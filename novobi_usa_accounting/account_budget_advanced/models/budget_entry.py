# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import xlsxwriter
import re
import io
import ast
from odoo import models, api, _, fields
from odoo.tools import relativedelta
from dateutil import rrule
from datetime import timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import ValidationError
from ..utils.budget_utils import _divide_line, _get_balance_sheet_value, get_list_period_by_type
from xlsxwriter import utility


class BudgetEntry(models.AbstractModel):
    _inherit = 'account.report'
    _name = 'usa.budget.entry'
    _description = 'Budget Entry'

    def _get_templates(self):
        templates = super(BudgetEntry, self)._get_templates()
        templates['line_template'] = 'account_budget_advanced.line_template_budget_entry_screen'
        templates['main_template'] = 'account_budget_advanced.template_budget_entry_screen'
        return templates

    def _get_report_name(self):
        budget_wizard, import_data = self._get_budget_wizard_obj()
        return budget_wizard.crossovered_budget_id.name if budget_wizard.crossovered_budget_id else budget_wizard.name

    def get_report_filename(self, options):
        """The name that will be used for the file when downloading pdf,xlsx,..."""
        if options and options.get('crossovered_budget_id', False):
            budget = self.env['crossovered.budget'].browse(options['crossovered_budget_id'])
            return budget.name.lower().replace(' ', '_')

    def _get_columns_name(self, options, export=None, budget=None):
        columns = [{'name': 'Account'}]

        daterange_list = options.get('daterange_list', False)
        budget = budget or options['crossovered_budget']

        if export:
            daterange_list = self._get_daterange_list(budget.date_from, budget.date_to)

        for item in daterange_list:
            columns.append({'name': item[0].strftime("%b %Y"), 'class': 'number value_column '})

        # for dt in rrule.rrule(rrule.MONTHLY, dtstart=budget.date_from, until=budget.date_to):
        #     columns.append({'name': dt.strftime("%b %Y"), 'class': 'number value_column '})

        if budget.budget_type == 'profit':
            columns.append({'name': 'Total', 'class': 'number total_column', 'total_column': True})

        return columns

    def _get_reports_buttons(self):
        return []

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = options.get('lines', {})

        return lines

    def _get_dict_lines(self, children_lines, column_number, budget_wizard, index_dict, import_data,
                        financial_report, currency_table, daterange_list, is_profit_budget):
        final_result_table = []
        budget_position_list = []
        result_actual_data = {}
        AccountAccount = self.env['account.account']
        crossovered_budget_id = budget_wizard.crossovered_budget_id
        analytic_account_id = crossovered_budget_id.analytic_account_id if crossovered_budget_id \
            else budget_wizard.analytic_account_id
        empty = [0.0 for i in range(column_number)]

        # build comparison table
        for line in children_lines:
            domain_ids = {}
            actual_data = {}

            if line.hide_in_budget:
                continue

            # Post-processing ; creating line dictionnary, building comparison, computing total for extended, formatting
            vals = {
                'id': line.id,
                'name': line.name,
                'level': line.level,
                'unfoldable': len(domain_ids) > 1 and line.show_domain != 'always',
                'columns': [{'name': 0} for i in range(column_number)] if not line.domain else [],
            }

            if line.action_id:
                vals['action_id'] = line.action_id.id
            if line.financial_report_id:
                vals['total_id'] = str(line.id)
            if line.formulas and not line.domain:
                vals['formulas'] = line.formulas.split('=')[1].replace('.balance', '')
            if line.code and not line.domain:
                vals['code'] = line.code

            lines = [vals]
            groupby = line.groupby or 'aml'

            if line.domain:
                edit_domain = line.domain.replace('account_id.', '')
                domain_ids = sorted(AccountAccount.search(ast.literal_eval(edit_domain)).ids)
                if index_dict:
                    if is_profit_budget:
                        actual_data = self._get_actual_data(ast.literal_eval(line.domain), budget_wizard,
                                                            column_number, index_dict, line.green_on_positive)

                    else:
                        actual_data = _get_balance_sheet_value(line, financial_report, currency_table, daterange_list,
                                                               analytic_account_id, last_year=True)

                    result_actual_data.update(actual_data)

            for domain_id in domain_ids:
                name = str(line._get_gb_name(domain_id))

                # create budget position for each account
                budget_position_list += self._create_budget_position(domain_id, name, line.green_on_positive)

                # get values from excel file, or crossovered_budget, or actual data
                try:
                    columns = []
                    if import_data:
                        columns = import_data.get(str(domain_id), [])[2:]
                    elif index_dict:
                        columns = actual_data.get(domain_id, empty)
                    elif crossovered_budget_id:
                        amount_field_name = 'planned_amount' if line.green_on_positive else 'planned_amount_entry'
                        columns = crossovered_budget_id.crossovered_budget_line.filtered(lambda x: domain_id in x.general_budget_id.account_ids.ids).\
                            sorted(lambda x: x.date_from).mapped(amount_field_name)
                        if crossovered_budget_id.budget_type == 'profit':
                            columns.append(0)  # for total column

                    if not columns:
                        columns = empty

                    vals = {
                        'id': domain_id,
                        'account_id': domain_id,
                        'name': name and len(name) >= 45 and name[0:40] + '...' or name,
                        'level': 4,
                        'parent_id': line.id,
                        'columns': [{'name': "{0:,.2f}".format(i)} for i in columns],
                        'caret_options': groupby == 'account_id' and 'account.account' or groupby,
                    }

                except Exception as error:
                    if import_data:
                        raise ValidationError(_("""Sorry! We couldn't import this file.\n
                        Please make sure you use the correct template from our export feature."""))

                    raise ValidationError(error)

                lines.append(vals)

            if domain_ids:  # total-line of sub lines => don't need formula
                lines.append({
                    'id': 'total_' + str(line.id),
                    'total_id': str(line.id),
                    'code': line.code,
                    'name': _('Total') + ' ' + line.name,
                    'class': 'o_account_reports_domain_total',
                    'columns': [{'name': 0} for i in range(column_number)],
                })

            if len(lines) == 1:
                new_lines, new_budget_list, \
                new_actual_data = self._get_dict_lines(line.children_ids, column_number, budget_wizard, index_dict,
                                                       import_data, financial_report, currency_table,
                                                       daterange_list, is_profit_budget)
                budget_position_list += new_budget_list
                result_actual_data.update(new_actual_data)
                if new_lines and line.level > 0 and line.formulas:
                    divided_lines = _divide_line(lines[0], column_number, line)
                    result = [divided_lines[0]] + new_lines + [divided_lines[1]]
                else:
                    result = []
                    if line.level > 0:
                        result += lines
                    result += new_lines
                    if line.level <= 0:
                        result += lines
            else:
                result = lines
            final_result_table += result

        return final_result_table, budget_position_list, result_actual_data

    def get_html(self, options, line_id=None, additional_context=None):
        if additional_context is None:
            additional_context = {}

        budget_wizard, import_data = self._get_budget_wizard_obj()
        is_profit_budget = True if budget_wizard.budget_type == 'profit' else False

        financial_report = self.env.ref('account_reports.account_financial_report_profitandloss0') \
            if budget_wizard.budget_type == 'profit' \
            else self.env.ref('account_reports.account_financial_report_balancesheet0')
        currency_table = financial_report._get_currency_table()

        # get lines, put it here because we need to create the budget before _get_lines.
        daterange_list = self._get_daterange_list(budget_wizard.start_date, budget_wizard.end_date)
        column_number = (len(daterange_list) + 1) if is_profit_budget else len(daterange_list)

        # to quickly get index when get previous data + create new budget
        index_dict = self._create_index_dict(budget_wizard) if budget_wizard.previous_data else {}

        # get lines
        lines, budget_position_list, actual_data = self._get_dict_lines(financial_report.line_ids, column_number,
                                                                        budget_wizard, index_dict, import_data,
                                                                        financial_report, currency_table,
                                                                        daterange_list, is_profit_budget)

        # create crossovered_budget
        budget = budget_wizard.crossovered_budget_id if budget_wizard.crossovered_budget_id \
            else self._create_crossovered_budget(budget_position_list, budget_wizard, actual_data, index_dict, daterange_list)

        # add more options
        options.update({
            'column_number': column_number,
            'lines': lines,
            'crossovered_budget': budget,
            'crossovered_budget_id': budget.id,
            'budget_wizard_id': budget_wizard.id,
            'daterange_list': daterange_list,
            'save_budget_import': True if import_data else False,
        })

        additional_context.update({
            'budget_entry': True,
            'crossovered_budget': budget,
            'currency_id': self.env.company.currency_id

        })

        return super(BudgetEntry, self).get_html(options, line_id=line_id,
                                                 additional_context=additional_context)

    def get_xlsx(self, options):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Sheet 1')
        budget = self.env['crossovered.budget'].browse(options['crossovered_budget_id'])

        # Styles
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10})
        header_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True})
        subtotal_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'bottom': 1})
        formula_total_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'bottom': 6})

        default_style.set_locked(False)
        default_style.set_num_format('#,##0.00')
        subtotal_style.set_num_format('#,##0.00')
        formula_total_style.set_num_format('#,##0.00')

        # Set the first column width to 50
        sheet.set_column(1, 1, 50)
        sheet.set_column(2, 50, 15)

        # Write the headers
        headers = self._get_columns_name(options, export=True, budget=budget)
        sheet.write_row(0, 1, [i['name'] for i in headers], header_style)

        # Start from the first cell. Rows and columns are zero indexed,
        # but we use the 1st column for ID, so now col's 1-indexed.
        data = options.get('data', [])
        row = 1
        sum_row_index = -1
        code_dict = {}
        regex = re.compile("\+|-|\s")

        # Iterate over the data and write it out row by row.
        for row_dict in data:
            col = 1
            sheet.write(row, 0, row_dict['account_id'])

            row_data = row_dict['data']

            if row_dict['code']:  # determine the row of the subtotal line
                code_dict[row_dict['code']] = row

            if row_dict['parent_id']:  # normal line
                if sum_row_index == -1:
                    sum_row_index = row
                sheet.write_row(row, col, row_data, default_style)

                # rewrite the total row at the last column
                if budget.budget_type == 'profit':
                    cell_range = utility.xl_range(row, 2, row, len(row_data)-1)
                    sheet.write_formula(row, len(row_data), '=SUM(' + cell_range + ')',
                                        default_style, float(row_data[len(row_data)-1]))

            elif row_dict['total_id'] and not row_dict['formulas']:  # total by sum
                sheet.write(row, col, row_data[0], subtotal_style)
                col += 1

                for i in range(len(row_data)-1):
                    cell_range = utility.xl_range(sum_row_index, col, row-1, col)
                    sheet.write_formula(row, col, '=SUM(' + cell_range + ')', subtotal_style, float(row_data[col-1]))
                    col += 1
                sum_row_index = -1

            elif row_dict['formulas']:  # total by formula
                sheet.write(row, col, row_data[0], formula_total_style)
                col += 1

                codes = regex.split(row_dict['formulas'].replace(' ', ''))

                for i in range(len(row_data) - 1):
                    formula = row_dict['formulas']
                    for code in codes:
                        formula = formula.replace(code, utility.xl_rowcol_to_cell(code_dict[code], col) if code_dict.get(code) else str(0), 1)
                    sheet.write_formula(row, col, '=' + formula, formula_total_style, float(row_data[col-1]))
                    col += 1
                sum_row_index = -1
                row += 1
            else:  # title line
                sheet.write_row(row, col, row_data, header_style)
            row += 1

        sheet.set_column('A:A', None, None, {'hidden': 1})  # hide ID column
        sheet.protect()

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file

    # HELPER FUNCTION
    def _get_daterange_list(self, date_from, date_to):
        daterange_list = get_list_period_by_type(date_from, date_to, "BY_MONTH")

        return daterange_list

    def _get_budget_wizard_obj(self):
        budget_wizard_id = self.env.context.get('budget_wizard_id', False)
        import_data = self.env.context.get('import_data', False)
        params = self.env.context.get('params', False)

        if not budget_wizard_id and params and params.get('action', False):
            action_obj = self.env['ir.actions.client'].browse(params['action'])
            budget_wizard_id = action_obj.params.get('budget_wizard_id', False)

        budget_wizard = self.env['account.budget.wizard'].browse(budget_wizard_id)

        return budget_wizard, import_data

    def _create_budget_position(self, account_id, account_name, green_on_positive):
        # create budget position for each account
        BudgetPosition = self.env['account.budget.post']
        budget_position = BudgetPosition.search([('account_ids', '=', account_id)])

        if budget_position and budget_position.filtered(lambda budget: len(budget.account_ids) == 1):
            return budget_position.filtered(lambda budget: len(budget.account_ids) == 1)[0]  # return only 1
        else:
            return BudgetPosition.create({'name': account_name,
                                          'account_ids': [(6, 0, [account_id])],
                                          'positive_account': green_on_positive})

    def _create_crossovered_budget(self, budget_position_list, budget_wizard, actual_data, index_dict, daterange_list):
        Budget = self.env['crossovered.budget']
        budget_lines = []

        time_period = []

        for item in daterange_list:
            time_period.append({'date_from': item[0], 'date_to': item[1]})

        for position in budget_position_list:
            account_id = position.account_ids[0].id
            account_actual_data = actual_data.get(account_id, False)

            for period in time_period:
                # we use the same time index of loading previous data, so year-1
                time_index = str(period['date_from'].month) + '-' + str(period['date_from'].year-1)
                amount = account_actual_data[index_dict[time_index]] if account_actual_data else 0

                line_dict = {'general_budget_id': position.id,
                             'planned_amount_entry': amount,
                             'analytic_account_id': budget_wizard.analytic_account_id.id}
                line_dict.update(period)
                budget_lines.append(line_dict)

        budget = Budget.create({'name': budget_wizard.name,
                                'date_from': budget_wizard.start_date,
                                'date_to': budget_wizard.end_date,
                                'budget_type': budget_wizard.budget_type,
                                'analytic_account_id': budget_wizard.analytic_account_id.id,
                                'crossovered_budget_line': [(0, 0, line) for line in budget_lines]})

        budget_wizard.crossovered_budget_id = budget  # link budget, for refresh the page + delete the budget

        return budget

    def _create_index_dict(self, budget_wizard):
        """
        To quickly determine the index based on year and month
        """
        index_dict = {}
        for index, dt in enumerate(rrule.rrule(rrule.MONTHLY, dtstart=budget_wizard.previous_start_date,
                                               until=budget_wizard.previous_end_date)):
            index_dict[str(dt.month) + '-' + str(dt.year)] = index
        return index_dict

    @api.model
    def _get_actual_data(self, domain, budget_wizard, column_number, index_dict, green_on_positive):
        result_dict = {}

        tables, where_clause, where_params = self.env['account.move.line'].with_context(
            analytic_account_ids = budget_wizard.analytic_account_id)._query_get(domain=domain)
        sql_params = [budget_wizard.previous_start_date.strftime(DEFAULT_SERVER_DATE_FORMAT),
                       budget_wizard.previous_end_date.strftime(DEFAULT_SERVER_DATE_FORMAT)]
        sql_params.extend(where_params)
        sql_query = """
                SELECT "account_move_line".account_id as account_id, 
                    date_part('year', "account_move_line".date::date) as year,
                    date_part('month', "account_move_line".date::date) AS month,
                    SUM("account_move_line".balance) as total_balance,
                    SUM("account_move_line".debit) as debit,
                    SUM("account_move_line".credit) as credit
                    
                FROM "account_move" as "account_move_line__move_id","account_move_line" 
                
                WHERE ("account_move_line"."move_id"="account_move_line__move_id"."id") AND
                    "account_move_line".date >= %s AND
                    "account_move_line".date <= %s AND """ + where_clause + """
                    GROUP BY account_id, year, month 
                    ORDER BY account_id, year, month;
                    """
        self.env.cr.execute(sql_query, sql_params)
        result = self.env.cr.dictfetchall()

        for r in result:
            account_balance = result_dict.get(r['account_id'], [0.0 for i in range(column_number)])
            time_index = str(int(r['month'])) + '-' + str(int(r['year']))
            index = index_dict[time_index]
            account_balance[index] = r['credit'] - r['debit'] if green_on_positive else r['debit'] - r['credit']

            result_dict[r['account_id']] = account_balance

        return result_dict


