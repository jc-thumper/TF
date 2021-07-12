# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import random
import re
import ast
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.osv import expression

from ...l10n_custom_dashboard.utils.graph_setting import get_chartjs_setting, get_linechart_format, get_barchart_format, get_info_data, get_chart_json
from ..utils.graph_utils import get_json_render, get_json_data_for_selection, get_data_for_graph, append_data_fetch_to_list
from ..utils.time_utils import get_list_period_by_type, get_start_end_date_value, BY_DAY, BY_WEEK, BY_MONTH, BY_QUARTER, BY_YEAR, BY_FISCAL_YEAR
from ..utils.utils import get_list_companies_child

PRIMARY_GREEN = "#00A09D"
PRIMARY_PURPLE = "#875a7b"
PRIMARY_ORANGE = "#f19848"
PRIMARY_BLUE = "#649ce7"

COLOR_VALIDATION_DATA = "#337ab7"
COLOR_INCOME = PRIMARY_GREEN
COLOR_EXPENSE = PRIMARY_ORANGE
COLOR_SALE_PAST = PRIMARY_PURPLE
COLOR_SALE_FUTURE = PRIMARY_GREEN
COLOR_CASH_OUT = PRIMARY_ORANGE
COLOR_CASH_IN = PRIMARY_GREEN
COLOR_PROJECTED_CASH_IN = PRIMARY_GREEN
COLOR_PROJECTED_CASH_OUT = PRIMARY_ORANGE
COLOR_PROJECTED_BALANCE = PRIMARY_BLUE
COLOR_NET_CASH = PRIMARY_BLUE
COLOR_BANK = PRIMARY_GREEN
COLOR_BOOK = PRIMARY_ORANGE
COLOR_OPEN_INVOICES = PRIMARY_ORANGE
COLOR_PAID_INVOICE = PRIMARY_GREEN
COLOR_OPEN_BILLS = PRIMARY_PURPLE
COLOR_PAID_BILLS = PRIMARY_BLUE

PROFIT_LOT = 'profit_and_loss'
SALES = 'sales'
CASH = 'cash'
CASH_FORECAST = 'cash_forecast'
BANK = 'bank'
CUSTOMER_INVOICE = 'sale'
VENDOR_BILLS = 'purchase'

GRAPH_CONFIG = {
    PROFIT_LOT:         {'type': 'bar',             'function': 'retrieve_profit_and_loss'},
    SALES:              {'type': 'line',            'function': 'retrieve_sales'},
    CASH:               {'type': 'bar',             'function': 'retrieve_cash'},
    CASH_FORECAST:      {'type': 'bar',             'function': 'retrieve_cash_forecast'},
    BANK:               {'type': 'horizontalBar',   'function': ''},
    CUSTOMER_INVOICE:   {'type': 'bar',             'function': 'retrieve_account_invoice'},
    VENDOR_BILLS:       {'type': 'bar',             'function': 'retrieve_account_invoice'},
}


class USAJournal(models.Model):
    _name = "usa.journal"
    _description = "US Accounting journal"

    period_by_month = [{'n': 'This Month', 'd': 0, 't': BY_MONTH},
                       {'n': 'This Quarter', 'd': 0, 't': BY_QUARTER},
                       {'n': 'This Fiscal Year', 'd': 0, 't': BY_FISCAL_YEAR},
                       {'n': 'Last Month', 'd': -1, 't': BY_MONTH},
                       {'n': 'Last Quarter', 'd': -1, 't': BY_QUARTER},
                       {'n': 'Last Fiscal Year', 'd': -1, 't': BY_FISCAL_YEAR}, ]

    period_by_month_fiscal_year = [{'n': 'This Month', 'd': 0, 't': BY_MONTH, 'td': False},
                                   {'n': 'This Quarter', 'd': 0, 't': BY_QUARTER, 'td': False},
                                   {'n': 'This Year', 'd': 0, 't': BY_YEAR, 'td': False},
                                   {'n': 'Last Month', 'd': -1, 't': BY_MONTH, 'td': False},
                                   {'n': 'Last Quarter', 'd': -1, 't': BY_QUARTER, 'td': False},
                                   {'n': 'Last Fiscal Year', 'd': -1, 't': BY_YEAR, 'td': True}, ]

    period_by_complex = [{'n': 'This Week by Day', 'd': 0, 'k': BY_DAY, 't': BY_WEEK},
                         {'n': 'This Month by Week', 'd': 0, 'k': BY_WEEK, 't': BY_MONTH},
                         {'n': 'This Quarter by Month', 'd': 0, 'k': BY_MONTH, 't': BY_QUARTER},
                         {'n': 'This Fiscal Year by Month', 'd': 0, 'k': BY_MONTH, 't': BY_FISCAL_YEAR},
                         {'n': 'This Fiscal Year by Quarter', 'd': 0, 'k': BY_QUARTER, 't': BY_FISCAL_YEAR},
                         {'n': 'Last Week by Day', 'd': -1, 'k': BY_DAY, 't': BY_WEEK},
                         {'n': 'Last Month by Week', 'd': -1, 'k': BY_WEEK, 't': BY_MONTH},
                         {'n': 'Last Quarter by Month', 'd': -1, 'k': BY_MONTH, 't': BY_QUARTER},
                         {'n': 'Last Fiscal Year by Month', 'd': -1, 'k': BY_MONTH, 't': BY_FISCAL_YEAR},
                         {'n': 'Last Fiscal Year by Quarter', 'd': -1, 'k': BY_QUARTER, 't': BY_FISCAL_YEAR}, ]
    default_period_by_month = 'This Fiscal Year'
    default_period_complex = 'This Fiscal Year by Month'

    type_element = [
        (PROFIT_LOT, _('Profit and Loss')),
        (SALES, _('Sales')),
        (CASH, _('Cash')),
        (CASH_FORECAST, _('Cashflow Forecast'))
    ]

    code = fields.Char(string='Code', required=True)
    type = fields.Selection(type_element, required=True)
    name = fields.Char('Element Name', required=True)
    account_dashboard_graph_dashboard_graph = fields.Text(compute='compute_account_dashboard_graph', store=False)
    extend_data = fields.Boolean(compute='compute_account_dashboard_graph', default=False, store=True)
    show_on_dashboard = fields.Boolean(string='Show journal on dashboard', default=True,
                                       help="Whether this journal should be displayed on the dashboard or not")
    color = fields.Integer("Color Index", default=0)
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 default=lambda self: self.env.company, help="Company related to this journal")
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    recurring_cashin = fields.Monetary('Recurring Cash in', default=0)
    recurring_cashout = fields.Monetary('Recurring Cash out', default=0)

    @api.depends()
    def compute_account_dashboard_graph(self):
        for record in self:
            graph_data = None
            extend_mode = None
            selection = []
            extra_param = []

            if record.type == PROFIT_LOT:
                _, graph_data = record.get_general_kanban_section_data()
                get_json_data_for_selection(record, selection, record.period_by_month, record.default_period_by_month)

            if record.type == SALES:
                extend_mode, graph_data = record.get_general_kanban_section_data()
                get_json_data_for_selection(record, selection, record.period_by_complex, record.default_period_complex)

            if record.type == CASH:
                extend_mode, graph_data = record.get_general_kanban_section_data()
                get_json_data_for_selection(record, selection, record.period_by_complex, record.default_period_complex)

            if record.type == CASH_FORECAST:
                extend_mode, graph_data = record.get_general_kanban_section_data()
                # get_json_data_for_selection(self, selection, self.period_by_complex, self.default_period_complex)

            if record.type == BANK:
                extend_mode, graph_data = record.get_bar_by_category_graph_data()

            if record.type == CUSTOMER_INVOICE:
                extend_mode, graph_data = record.get_general_kanban_section_data()
                get_json_data_for_selection(record, selection, record.period_by_month_fiscal_year, record.default_period_by_month)
                extra_param.append(record.type)

            if record.type == VENDOR_BILLS:
                extend_mode, graph_data = record.get_general_kanban_section_data()
                get_json_data_for_selection(record, selection, record.period_by_month_fiscal_year, record.default_period_by_month)
                extra_param.append(record.type)

            if graph_data:
                graph_type = GRAPH_CONFIG[record.type].get('type', '')
                function_retrieve = GRAPH_CONFIG[record.type].get('function', '')
                record.account_dashboard_graph_dashboard_graph = json.dumps(
                    get_json_render(graph_type, False, '', graph_data, record.type, selection, function_retrieve, extra_param))
                record.extend_data = extend_mode

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    def comp_ins_action(self):
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Company Insight'),
            'res_model': 'usa.journal',
            'view_mode': 'kanban',
            'target': 'main',
        }
        return action

    def change_status_extend(self, extend):
        object_json = json.loads(self.account_dashboard_graph_dashboard_graph)
        object_json['extend'] = extend
        json_return = json.dumps(object_json)
        return json_return

    def get_bar_by_category_graph_data(self):
        data = []

        for i in range(10):
            value = random.randint(1, 100)
            label = 'label ' + str(value)
            data.append({'label': label, 'value': value, 'type': label})
        data = sorted(data, key=lambda v: v.get('value'), reverse=True)

        (graph_title, graph_key) = ('', '')
        extend_data = True if (len(data) > 5) else False
        return extend_data, [{
            'values': data,
            'title': graph_title,
            'key': graph_key,
            'color': COLOR_VALIDATION_DATA}]

    def get_general_kanban_section_data(self):
        data = []

        (graph_title, graph_key) = ('', '')
        extend_data = False
        return extend_data, [{
            'values': data,
            'title': graph_title,
            'key': graph_key,
            'color': COLOR_VALIDATION_DATA}]

    ########################################################
    # BUTTON EVENT
    ########################################################
    def action_extend_view(self):
        """ Function implement action click button is named 'EXTEND' in
        each kanban section

        :return:
        """
        pass

    def open_action_label(self):
        # TODO: fix action and complete_empty_list_help
        """ Function return action based on type for related journals

        :return:
        """
        self.ensure_one()
        action_name = self._context.get('action_name', False)
        domain = []
        action = None
        if not action_name:
            if self.type == PROFIT_LOT:
                action = self.env.ref('account_reports.account_financial_report_profitandloss0').generated_menu_id.action
                action_name = action.xml_id
            elif self.type == SALES:
                action_name = 'account.action_move_out_invoice_type'
                domain = [('type', '=', 'out_invoice')]
            elif self.type == CASH:
                # action = self.env.ref('account_reports.account_financial_report_cashsummary0').generated_menu_id.action
                action = self.env.ref('account_reports.action_account_report_cs')
                action_name = action.xml_id
            elif self.type == CUSTOMER_INVOICE:
                action_name = 'account.action_move_out_invoice_type'
                domain = [('type', '=', 'out_invoice')]
            elif self.type == VENDOR_BILLS:
                action_name = 'account.action_vendor_bill_template'
                domain = [('type', '=', 'in_invoice')]
            else:
                action_name = 'action_none'

        _journal_invoice_type_map = {
            (CUSTOMER_INVOICE, None): 'out_invoice',
            (SALES, None): 'out_invoice',
            (VENDOR_BILLS, None): 'in_invoice',
            (CUSTOMER_INVOICE, 'refund'): 'out_refund',
            (VENDOR_BILLS, 'refund'): 'in_refund',
            (BANK, None): BANK,
            (CASH, None): CASH,
            ('general', None): 'general',
        }
        if not action:
            journal_id = self.env['account.journal'].search([('type', '=', self.type)]).id
            invoice_type = _journal_invoice_type_map[(self.type, self._context.get('invoice_type'))]

            ctx = self._context.copy()
            ctx.pop('group_by', None)
            ctx.update({
                'journal_type': self.type,
                'default_journal_id': journal_id,
                'default_type': invoice_type,
                'type': invoice_type
            })
        else:
            ctx = action.context

        [action] = self.env.ref(action_name).read()

        # Copy and modify from file account_journal_dashboard.py
        if domain and self.type == VENDOR_BILLS:
            purchase_journal_id = self.env['account.journal'].search([('type', '=', 'purchase')]).id
            ctx['search_default_journal_id'] = purchase_journal_id

        action['context'] = ctx
        action['domain'] = domain

        # Copy and modify from file account_journal_dashboard.py
        account_invoice_filter = self.env.ref('account.view_account_invoice_filter', False)
        if self.type in [CUSTOMER_INVOICE, VENDOR_BILLS]:
            action['search_view_id'] = account_invoice_filter and account_invoice_filter.id or False

        if self.type == VENDOR_BILLS:
            new_help = self.env['account.move'].with_context(ctx).complete_empty_list_help()
            action.update({'help': action.get('help', '') + new_help})
        return action

    def action_create_new(self):
        """ Function implement action click button New "X" in Vendor bills and customer invoices

        :return:
        """
        self.ensure_one()
        ctx = self._context.copy()
        model = 'account.move'
        if self.type == CUSTOMER_INVOICE:
            sale_id = self.env['account.journal'].search([('type', '=', 'sale')]).id
            ctx.update({
                'journal_type': self.type,
                'default_type': 'out_invoice',
                'type': 'out_invoice',
                'default_journal_id': sale_id})
            if ctx.get('refund'):
                ctx.update({'default_type': 'out_refund', 'type': 'out_refund'})
            view_id = self.env.ref('account.view_move_form').id
        elif self.type == VENDOR_BILLS:
            purchase_id = self.env['account.journal'].search([('type', '=', 'purchase')]).id
            ctx.update({'journal_type': self.type,
                        'default_type': 'in_invoice',
                        'type': 'in_invoice',
                        'default_journal_id': purchase_id})
            if ctx.get('refund'):
                ctx.update({'default_type': 'in_refund', 'type': 'in_refund'})
            view_id = self.env.ref('account.view_move_form').id

        else:
            ctx.update({'default_journal_id': self.id, 'view_no_maturity': True})
            view_id = self.env.ref('account.view_move_form').id
            model = 'account.move'
        return {
            'name': _('Create invoice/bill'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': model,
            'view_id': view_id,
            'context': ctx,
        }

    def open_action(self):
        # TODO: fix action and complete_empty_list_help
        """return action based on type for related journals"""
        self.ensure_one()
        action_name = self._context.get('action_name', False)
        if not action_name:
            if self.type == BANK:
                action_name = 'action_bank_statement_tree'
            elif self.type == CUSTOMER_INVOICE:
                action_name = 'action_move_out_invoice_type'
                self = self.with_context(use_domain=[('type', '=', 'out_invoice')])
            elif self.type == VENDOR_BILLS:
                action_name = 'action_vendor_bill_template'
                self = self.with_context(use_domain=[('type', '=', 'in_invoice')])
            else:
                action_name = 'action_move_journal_line'

        _journal_invoice_type_map = {
            (CUSTOMER_INVOICE, None): 'out_invoice',
            (VENDOR_BILLS, None): 'in_invoice',
            (CUSTOMER_INVOICE, 'refund'): 'out_refund',
            (VENDOR_BILLS, 'refund'): 'in_refund',
            (BANK, None): BANK,
            (CASH, None): CASH,
            ('general', None): 'general',
        }
        invoice_type = _journal_invoice_type_map[(self.type, self._context.get('invoice_type'))]

        ctx = self._context.copy()
        ctx.pop('group_by', None)
        ctx.update({
            'journal_type': self.type,
            'default_journal_id': self.id,
            'default_type': invoice_type,
            'type': invoice_type
        })

        [action] = self.env.ref('account.%s' % action_name).read()
        if not self.env.context.get('use_domain'):
            ctx['search_default_journal_id'] = self.id
        action['context'] = ctx
        action['domain'] = self._context.get('use_domain', [])
        account_invoice_filter = self.env.ref('account.view_account_invoice_filter', False)
        if action_name in ['action_move_out_invoice_type', 'action_vendor_bill_template']:
            action['search_view_id'] = account_invoice_filter and account_invoice_filter.id or False
        if action_name in ['action_bank_statement_tree', 'action_view_bank_statement_tree']:
            action['views'] = False
            action['view_id'] = False
        if self.type == VENDOR_BILLS:
            new_help = self.env['account.move'].with_context(ctx).complete_empty_list_help()
            action.update({'help': action.get('help', '') + new_help})
        return action

    def action_open_reconcile(self):
        self.ensure_one()
        if self.type in [BANK]:
            # Open reconciliation view for bank statements belonging to this journal
            bank_stmt = self.env['account.bank.statement'].search([('journal_id', 'in', self.ids)])
            return {
                'type': 'ir.actions.client',
                'tag': 'bank_statement_reconciliation_view',
                'context': {
                    'statement_ids': bank_stmt.ids,
                    'company_ids': self.mapped('company_id').ids
                },
            }
        else:
            # Open reconciliation view for customers/suppliers
            action_context = {
                'show_mode_selector': False,
                'company_ids': self.env.company
            }
            if self.type == CUSTOMER_INVOICE:
                action_context.update({'mode': 'customers'})
            elif self.type == VENDOR_BILLS:
                action_context.update({'mode': 'suppliers'})
            return {
                'type': 'ir.actions.client',
                'tag': 'manual_reconciliation_view',
                'context': action_context,
            }

    def action_recurring_amount(self):
        self.ensure_one()
        action = self.env.ref('account_dashboard.usa_journal_recurring_payment_view_action').read()[0]
        action['res_id'] = self.id
        return action

    def button_save_recurring(self):
        return True

    ########################################################
    # INITIAL DATA
    ########################################################
    @api.model
    def init_data_usa_journal(self):
        print("init_data_usa_journal")
        usa_journal = self.env['usa.journal']
        types = [item[0] for item in self.type_element]
        dict_elem = dict(self.type_element)
        for journal_type in types:
            if journal_type != BANK:
                for com in self.env['res.company'].search([]):
                    usa_journal.create({
                        'type': journal_type,
                        'name': dict_elem[journal_type],
                        'code': journal_type.upper(),
                        'company_id': com.id
                    })
            else:
                # Append all the bank journal are exist to the usa journal
                banks = self.env['account.journal'].search([('type', '=', 'bank')])
                for bank in banks:
                    usa_journal.create({
                        'type': journal_type,
                        'name': bank.name,
                        'code': bank.code.upper() + str(bank.id),
                        'company_id': bank.company_id.id
                    })

    ########################################################
    # API
    ########################################################
    @api.model
    def retrieve_profit_and_loss(self, date_from, date_to, period_type=BY_MONTH):
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
        date_to = datetime.strptime(date_to, '%Y-%m-%d')

        # Profit and loss record in account reports
        pal = self.env.ref('account_reports.account_financial_report_profitandloss0')

        # Net Income record in account reports
        ni = self.env.ref('account_reports.account_financial_report_net_profit0')
        list_lines = pal.mapped('line_ids')

        # create the tree of formula to compute each group
        demo = list(list_lines)
        dict_journal_item = {}

        # Loop in the queue of report line saved in demo variable
        while len(demo):
            # pop at the head of queue
            line = demo.pop(0)
            dict_journal_item.setdefault(line.code, {'pos': 1, 'child': [], 'code': line.code})

            # push all childes of report line have get from the variable 'line' at tail of queue
            demo += list(line.children_ids)
            # Remove the tail (.xxx) of code variable and space.
            # The formula variable contain the formula is used to compute for variable before the equal symbol
            formula = re.sub(r'\.\w+', '', line.formulas.replace(' ', '')).split('=')[1]

            # Var 'codes' is a list containing all parameter in the formula
            codes = re.split("\W", formula)
            for code in codes:
                if code:
                    str_compute = ""
                    for val in codes:
                        if val:
                            str_compute += val + ('=1' if val == code else '=0') + '\r\n'
                    code_exec = compile(str_compute, '', 'exec')
                    exec(code_exec)
                    sum_value = eval(formula)

                    if code not in ['sum', 'sum_if_pos', 'sum_if_neg']:
                        child = dict_journal_item.setdefault(code, {'pos': 1, 'child': [], 'code': code})
                        child['pos'] = sum_value
                        dict_journal_item[line.code]['child'].append(child)

        code_group_expenses = []
        code_group_income = []

        # Get the tree of net profit and loss in dict_journal_item
        ni_tree = dict_journal_item[ni.code]
        stack_child = ni_tree['child']
        while len(stack_child):
            node = stack_child.pop()
            childs = node['child']
            if childs:
                for child in childs:
                    child['pos'] *= node['pos']
                stack_child += childs
            else:
                if node['pos'] > 0:
                    code_group_income.append(node['code'])
                else:
                    code_group_expenses.append(node['code'])

        env = self.env['account.financial.html.report.line']

        domain_group_expenses = env.search([('code', 'in', code_group_expenses)]).mapped(lambda g: ast.literal_eval(g.domain))
        domain_group_income = env.search([('code', 'in', code_group_income)]).mapped(lambda g: ast.literal_eval(g.domain))

        expenses_domain = expression.OR(domain_group_expenses)
        income_domain = expression.OR(domain_group_income)
        tables, query_expenses_clause, where_params = self.env["account.move.line"]._query_get(domain=expenses_domain)

        sql_params = [period_type, date_from, date_to]
        sql_params.extend(where_params)

        income_group_data = self.env['account.move.line'].summarize_group_account(date_from, date_to, period_type, income_domain)
        expense_group_data = self.env['account.move.line'].summarize_group_account(date_from, date_to, period_type, expenses_domain)

        total_income, income_values, labels = get_data_for_graph(self, date_from, date_to, period_type, income_group_data, ['total_balance'], pos=-1)
        total_expense, expense_values, labels = get_data_for_graph(self, date_from, date_to, period_type, expense_group_data, ['total_balance'])

        graph_data = [
            get_barchart_format(income_values[0], _('Income'), COLOR_INCOME),
            get_barchart_format(expense_values[0], _('Expenses'), COLOR_EXPENSE),
        ]

        info_data = [
            get_info_data(self, _('Income'), total_income[0]),
            get_info_data(self, _('Expenses'), total_expense[0]),
            get_info_data(self, _('Net Income'), total_income[0] - total_expense[0]),
        ]

        return get_chart_json(graph_data, labels, get_chartjs_setting(chart_type='bar'), info_data)

    @api.model
    def retrieve_sales(self, date_from, date_to, period_type):
        """ API is used to response untaxed amount of all invoices in system that get
        from account_invoice.
        :param date_from: the start date to summarize data, have type is datetime
        :param date_to: the end date to summarize data, that have type is datetime
        :param period_type: is type of period to summarize data, we have 4 selections are
                ['week', 'month', 'quarter', 'year']
        :return: Json
        """
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
        date_to = datetime.strptime(date_to, '%Y-%m-%d')
        periods = get_list_period_by_type(self, date_from, date_to, period_type)

        currency = """
            SELECT c.id, COALESCE((
                SELECT r.rate
                FROM res_currency_rate r
                WHERE r.currency_id = c.id AND r.name <= %s AND (r.company_id IS NULL OR r.company_id IN %s)
                ORDER BY r.company_id, r.name DESC
                LIMIT 1), 1.0) AS rate
            FROM res_currency c
        """

        transferred_currency = """
            SELECT ai.invoice_date, ai.type, c.rate * ai.amount_untaxed AS amount_tran, state, company_id
            FROM account_move AS ai
                LEFT JOIN ({currency_table}) AS c ON ai.currency_id = c.id
        """.format(currency_table=currency)

        query = """
            SELECT date_part('year', aic.invoice_date::DATE) AS year,
                date_part(%s, aic.invoice_date::DATE) AS period,
                MIN(aic.invoice_date) AS date_in_period,
                SUM(aic.amount_tran) AS amount_untaxed
            FROM ({transferred_currency_table}) AS aic
            WHERE invoice_date >= %s AND
                invoice_date <= %s AND
                aic.state = 'posted' AND
                aic.type = 'out_invoice' AND
                aic.company_id IN %s
            GROUP BY year, period
            ORDER BY year, period;
        """.format(transferred_currency_table=transferred_currency)

        company_ids = self.env.companies.ids
        name = fields.Date.today()
        self.env.cr.execute(query, (period_type, name, tuple(company_ids), date_from, date_to, tuple(company_ids),))
        data_fetch = self.env.cr.dictfetchall()

        data_list = [[], []]
        graph_label = []
        index = 0
        total_sales = 0

        today = date.today()
        for data in data_fetch:
            while not (periods[index][0] <= data['date_in_period'] <= periods[index][1]) and index < len(periods):
                values = [
                    0 if periods[index][0] <= today else 'NaN',
                    0 if periods[index][1] >= today else 'NaN'
                ]
                append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=values)
                index += 1

            if index < len(periods):
                value = data.get('amount_untaxed', False)
                values = [
                    value if not isinstance(value, bool) and periods[index][0] <= today else 'NaN',
                    value if not isinstance(value, bool) and periods[index][1] >= today else 'NaN'
                ]
                total_sales += value if value else 0
                append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=values)
                index += 1

        while index < len(periods):
            values = [
                0 if periods[index][0] <= today else 'NaN',
                0 if periods[index][1] >= today else 'NaN'
            ]
            append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=values)
            index += 1

        graph_data = [
            get_linechart_format(data=data_list[0], label=_('Sales'), color=COLOR_SALE_PAST),
            get_linechart_format(data=data_list[1], label=_('Future'), color=COLOR_SALE_FUTURE),
        ]

        info_data = [get_info_data(self, _('Total Amount'), total_sales)]

        return get_chart_json(graph_data, graph_label, get_chartjs_setting(chart_type='line'), info_data)

    @api.model
    def retrieve_cash(self, date_from, date_to, period_type):
        """ API is used to response total amount of cash in/out base on
        account move in system. That is the account move of account have
        name is 'Bank and Cash' in the system beside that, also return
        any info relate to show in "Cash" kanban section.

        :param date_from: the start date to summarize data, have type is datetime
        :param date_to: the end date to summarize data, that have type is datetime
        :param period_type: is type of period to summarize data, we have 4 selections are
                ['week', 'month', 'quarter', 'year']
        :return: Json
        """

        date_from = datetime.strptime(date_from, '%Y-%m-%d')
        date_to = datetime.strptime(date_to, '%Y-%m-%d')
        periods = get_list_period_by_type(self, date_from, date_to, period_type)
        type_account_id = self.env.ref('account.data_account_type_liquidity').id
        query = """
            SELECT date_part('year', aml.date::DATE) AS year,
                date_part(%s, aml.date::DATE) AS period,
                MIN(aml.date) AS date_in_period,
                SUM(aml.debit) AS total_debit,
                SUM(aml.credit) AS total_credit
            FROM account_move_line AS aml
                INNER JOIN account_move AS am ON aml.move_id = am.id
                INNER JOIN account_account AS aa ON aml.account_id = aa.id
                INNER JOIN account_account_type AS aat ON aa.user_type_id = aat.id
            WHERE aml.date >= %s AND 
                aml.date <= %s AND
                am.state = 'posted' AND
                aat.id = %s AND 
                aml.company_id IN %s
            GROUP BY year, period
            ORDER BY year, period;
        """

        company_ids = self.env.companies.ids
        self.env.cr.execute(query, (period_type, date_from, date_to, type_account_id, tuple(company_ids),))
        data_fetch = self.env.cr.dictfetchall()

        data_list = [[], [], []]
        graph_label = []
        index = 0

        for data in data_fetch:
            while not (periods[index][0] <= data['date_in_period'] <= periods[index][1]) and index < len(periods):
                append_data_fetch_to_list(data_list, graph_label, periods, period_type, index)
                index += 1
            if index < len(periods):
                values = [data['total_debit'], -data['total_credit'], data['total_debit'] - data['total_credit']]
                append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=values)
                index += 1

        while index < len(periods):
            append_data_fetch_to_list(data_list, graph_label, periods, period_type, index)
            index += 1

        # Create chart data
        # Line chart must be on top of bar chart, so put it first and reverse the order of chart's legend
        graph_data = [
            get_linechart_format(data_list[2], _('Net cash'), COLOR_NET_CASH, order=2),
            get_barchart_format(data_list[1], _('Cash out'), COLOR_CASH_OUT, order=1),
            get_barchart_format(data_list[0], _('Cash in'), COLOR_CASH_IN),
        ]

        # Create info to show in head of chart
        info_data = [
            get_info_data(self, _('Cash in'), sum(data_list[0])),
            get_info_data(self, _('Cash out'), sum(data_list[1])),
            get_info_data(self, _('Net cash'), sum(data_list[0] + data_list[1])),
        ]

        return get_chart_json(graph_data, graph_label, get_chartjs_setting(chart_type='bar', mode='index', stacked=True, reverse=True), info_data)

    @api.model
    def retrieve_cash_forecast(self, date_from, date_to, period_type):
        company_ids = get_list_companies_child(self.env.company)
        receivable_account_id = self.env.ref('account.data_account_type_receivable').id
        payable_account_id = self.env.ref('account.data_account_type_payable').id
        liquidity_account_id = self.env.ref('account.data_account_type_liquidity').id
        forecast_dashboard = self.search([('type', '=', CASH_FORECAST)], limit=1)

        date_from = datetime.now().replace(day=1)
        this_year = date_from.year
        period_type = 'month'
        start_date, date_to = get_start_end_date_value(self, date_from + relativedelta(months=6), period_type)
        periods = get_list_period_by_type(self, date_from, date_to, period_type)
        data_dict = {}

        def _update_data_dict(data_dict, data_query, side='receivable'):
            for data in data_query:
                year = int(data['year'])
                period = int(data['period'])
                # key = int("{}{}".format(year, period))
                key = (year - this_year) * 20 + period
                if key not in data_dict:
                    data_dict[key] = {
                        'period': period,
                        'year': year
                    }
                data_dict[key][side] = data['amount']
            return data_dict

        def _get_bank_balance(date, account_type, company_ids):
            query = """SELECT COALESCE(SUM(aml.balance), 0) as balance
                        FROM account_move_line as aml
                        INNER JOIN account_move as am
                            ON aml.move_id = am.id
                        INNER JOIN account_account as aa
                            ON aml.account_id = aa.id
                        WHERE aml.date <= %s AND
                              am.state = 'posted' AND
                              aa.user_type_id = %s AND 
                              aml.company_id IN %s;"""
            self.env.cr.execute(query, (date, account_type, tuple(company_ids)))
            return self.env.cr.dictfetchall()

        def _get_account_balance(where, period_type, date_from, date_to, reconcile_acc_id, liquidity_account_id, company_ids):
            query = """
                SELECT date_part('year', aml.date_maturity) AS year,
                    date_part(%s, aml.date_maturity) AS period,
                    COALESCE(SUM(aml.amount_residual), 0) AS amount
                FROM account_move_line AS aml
                    INNER JOIN account_move AS am ON aml.move_id = am.id
                    INNER JOIN account_account AS aa ON aml.account_id = aa.id
                WHERE aml.date_maturity >= %s AND
                    aml.date_maturity <= %s AND
                    am.state = 'posted' AND
                    aml.company_id IN %s AND
                    (aa.user_type_id = %s OR (aa.user_type_id = %s AND {}))
                GROUP BY year, period
                ORDER BY year, period;
            """

            self.env.cr.execute(query.format(where), (period_type, date_from, date_to,  tuple(company_ids), reconcile_acc_id, liquidity_account_id))
            return self.env.cr.dictfetchall()

        # Projected Cash in = Debit of Receivable (Invoice) + Debit of Bank (Payment + Receipt)
        data_receivable = _get_account_balance('aml.debit > 0', period_type, date_from, date_to,
                                               receivable_account_id, liquidity_account_id, company_ids)
        data_dict = _update_data_dict(data_dict, data_receivable, 'receivable')

        # Projected Cash out = Credit of Payable (Bill) + Credit of Bank (Payment + Receipt)
        data_payable = _get_account_balance('aml.credit > 0', period_type, date_from, date_to,
                                            payable_account_id, liquidity_account_id, company_ids)
        data_dict = _update_data_dict(data_dict, data_payable, 'payable')

        opening_balance = _get_bank_balance(date_from, liquidity_account_id, company_ids)[0]['balance']

        recurring_cashin = forecast_dashboard.recurring_cashin
        recurring_cashout = forecast_dashboard.recurring_cashout * -1

        data_list = [[], [], []]
        graph_label = []
        index = 0

        for key in sorted(data_dict):
            data = data_dict[key]
            receivable = data.get('receivable', 0) + recurring_cashin
            payable = data.get('payable', 0) + recurring_cashout
            while not (periods[index][0].month <= data['period'] <= periods[index][1].month) and index < len(periods):
                opening_balance += recurring_cashin + recurring_cashout
                values = [recurring_cashin, recurring_cashout, opening_balance]
                append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=values)
                index += 1
            if index < len(periods):
                opening_balance += receivable + payable
                values = [receivable, payable, opening_balance]
                append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=values)
                index += 1

        while index < len(periods):
            opening_balance += recurring_cashin + recurring_cashout
            values = [recurring_cashin, recurring_cashout, opening_balance]
            append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=values)
            index += 1

        graph_data = [
            get_linechart_format(data_list[2], _('Balance'), COLOR_PROJECTED_BALANCE, order=2),
            get_barchart_format(data_list[1], _('Projected Cash out'), COLOR_PROJECTED_CASH_OUT, order=1),
            get_barchart_format(data_list[0], _('Projected Cash in'), COLOR_PROJECTED_CASH_IN),
        ]

        info_data = [
            get_info_data(self, _('Projected Cash in'), sum(data_list[0])),
            get_info_data(self, _('Projected Cash out'), sum(data_list[1])),
            get_info_data(self, _('Balance'), sum(data_list[0] + data_list[1])),
        ]

        return get_chart_json(graph_data, graph_label, get_chartjs_setting(chart_type='bar', mode='index', stacked=True, reverse=True), info_data)
