# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging


class AdvancedCashFlowReport(models.AbstractModel):
    _name = 'advanced.cash.flow.report'
    _description = 'Advanced Cash Flow Report'
    _inherit = 'account.cash.flow.report'

    filter_comparison = {'date_from': '', 'date_to': '', 'filter': 'no_comparison', 'number_period': 1}

    @api.model
    def _get_group_per_account(self, options):
        """ Compute a map account_id => CS_line_id used to dispatch the lines in the cash flow statement:
        This part is done in sql to avoid browsing and prefetching all account.account records.
        :param options: The report options.
        :param group_ids: The ids of the all the cashflow line that have accounts under
        :return:        A map account_id => group_id set on this account.
        """
        group_per_accounts = {}

        query = '''
                SELECT id, cashflow_structure_line_id
                FROM account_account
                WHERE cashflow_structure_line_id IS NOT NULL
                GROUP BY id
            '''

        self._cr.execute(query)
        for account_id, group_id in self._cr.fetchall():
            group_per_accounts[account_id] = group_id
        return group_per_accounts

    @api.model
    def _update_comparison_options(self, options, period_dict):
        # Update date_from and date_to for each comparison period
        new_options = options.copy()

        new_options['date'] = {
            'mode': 'range',
            'date_from': period_dict['date_from'],
            'date_to': period_dict['date_to'],
            'strict_range': period_dict['date_from'] is not False,
        }
        new_options['journals'] = []

        return new_options

    # Override
    @api.model
    def _get_columns_name(self, options):
        # Copy from account.financial.html.report
        columns = [{'name': ''}]

        columns += [{'name': self.format_date(options), 'class': 'number'}]
        if options.get('comparison') and options['comparison'].get('periods'):
            for period in options['comparison']['periods']:
                columns += [{'name': period.get('string'), 'class': 'number'}]
            # if options['comparison'].get('number_period') == 1 and not options.get('groups'):
            #     columns += [{'name': '%', 'class': 'number'}]

        if options.get('groups', {}).get('ids'):
            columns_for_groups = []
            for column in columns[1:]:
                for ids in options['groups'].get('ids'):
                    group_column_name = ''
                    for index, id in enumerate(ids):
                        column_name = self._get_column_name(id, options['groups']['fields'][index])
                        group_column_name += ' ' + column_name
                    columns_for_groups.append({'name': column.get('name') + group_column_name, 'class': 'number'})
            columns = columns[:1] + columns_for_groups

        return columns

    @api.model
    def _get_lines_to_compute(self, options, no_of_periods):
        """
        Get the structure lines of CS report
        :return:
        rows: list of dictionary represents the lines in report
        index_dict: dictionary to access the line index, so we can append sub-lines later
        main_lines: list of all main lines (in cash flow structure) => calculate net cash
        """

        def _get_line_id(line):
            return 'line_{}'.format(line.id)

        def _get_children_lines(current_line, parent_id=None):
            line_id = _get_line_id(current_line)
            data = {'id': line_id,
                    'name': current_line.name,
                    'level': current_line.level,
                    'columns': [{'name': 0.0, 'class': 'number'} for i in range(no_of_periods)],
                    'has_total_line': True if current_line.has_total_line else False,
                    }
            if parent_id:
                data['parent_id'] = parent_id
            index_dict[line_id] = len(rows)
            rows.append(data)

            for sub_line in current_line.child_ids.sorted(key='sequence'):
                if sub_line.child_ids:
                    _get_children_lines(sub_line, line_id)
                else:
                    sub_line_id = _get_line_id(sub_line)
                    index_dict[sub_line_id] = len(rows)
                    rows.append({'id': sub_line_id,
                                 'parent_id': line_id,
                                 'name': sub_line.name,
                                 'level': sub_line.level,
                                 'columns': [{'name': 0.0, 'class': 'number'} for i in range(no_of_periods)],
                                 'has_total_line': True if sub_line.has_total_line else False,
                                 })

        def _append_fixed_lines(fixed_lines):
            for index, level, name, class_name in fixed_lines:
                line_id = 'line_%s' % index
                index_dict[line_id] = len(rows)
                rows.append({'id': line_id,
                             'name': name,
                             'level': level,
                             'class': class_name,
                             'columns': [{'name': 0.0, 'class': 'number {}'.format(class_name)}
                                         for i in range(no_of_periods)]
                             })

        rows = []
        index_dict = {}
        main_lines = []
        top_fixed_rows = [
            ('begin', 2, _('Cash and cash equivalents, beginning of period'), ''),
            ('ar', 2, _('Advance Payments received from customers'), 'account_report_padding_top'),
            ('ap', 2, _('Advance Payments made to suppliers'), ''),
        ]
        btm_fixed_rows = [
            ('other', 2, _('Other Transactions'), ''),
            ('net', 0, _('NET CASH'), ''),
            ('end', 2, _('Cash and cash equivalents, closing balance'), 'account_report_padding_top'),
        ]
        _append_fixed_lines(top_fixed_rows)

        # Structure Lines
        structure_id = self.env.ref('novobi_cash_flow_statement.cash_flow_report_structure_record',
                                    raise_if_not_found=False)
        if not structure_id:
            structure_id = self.env['cash.flow.report.structure'].sudo().search([], limit=1)
        if structure_id:
            for line in structure_id.line_ids.sorted(key='sequence'):
                _get_children_lines(line)
                main_lines.append(_get_line_id(line))

        # Btm fixed rows
        _append_fixed_lines(btm_fixed_rows)

        return rows, index_dict, main_lines

    @api.model
    def _get_lines(self, options, line_id=None):

        def _get_amount_from_id(line_id, period):
            line = lines_to_compute[index_dict[line_id]]
            amount = line['columns'][period]['name']
            return line, amount

        def _insert_at_index(index, account_id, account_code, account_name, amount, period):
            # Insert the amount in the right section depending the line's index and the account_id.
            # Helper used to add some values to the report line having the index passed as parameter
            # (see _get_lines_to_compute).
            line = lines_to_compute[index]

            if self.env.user.company_id.currency_id.is_zero(amount):
                return

            line.setdefault('unfolded_lines', {})
            line['unfolded_lines'].setdefault(account_id, {
                'id': account_id,
                'name': '%s %s' % (account_code, account_name),
                'level': line['level'] + 1,
                'parent_id': line['id'],
                'columns': [{'name': 0.0, 'class': 'number'} for i in range(no_of_periods)],
                'caret_options': 'account.account',
            })
            line['columns'][period]['name'] += amount
            line['unfolded_lines'][account_id]['columns'][period]['name'] += amount

        def _dispatch_result(account_id, account_code, account_name, account_internal_type, amount, period):
            """Dispatch the newly fetched line inside the right section. """
            if account_internal_type == 'receivable':
                # 'Advance Payments received from customers'                (index=3)
                _insert_at_index(index_dict['line_ar'], account_id, account_code, account_name, -amount, period)
            elif account_internal_type == 'payable':
                # 'Advance Payments made to suppliers'                      (index=5)
                _insert_at_index(index_dict['line_ap'], account_id, account_code, account_name, -amount, period)
            else:
                group_id = group_per_accounts.get(account_id, 'other')
                group_line_id = "line_{}".format(group_id)
                _insert_at_index(index_dict[group_line_id], account_id, account_code, account_name, -amount, period)

        # Comparison
        comparison_table = [options.get('date')]
        comparison_table += options.get('comparison') and options['comparison'].get('periods', []) or []
        no_of_periods = len(comparison_table)

        unfold_all = self._context.get('print_mode') or options.get('unfold_all')
        currency_table_query = self._get_query_currency_table(options)
        lines_to_compute, index_dict, main_lines = self._get_lines_to_compute(options, no_of_periods)
        group_per_accounts = self._get_group_per_account(options)

        # *************************************************
        # ****************** CALCULATION ******************
        # *************************************************
        period = 0  # index
        for period_dict in comparison_table:
            new_options = self._update_comparison_options(options, period_dict)

            payment_move_ids, payment_account_ids = self._get_liquidity_move_ids(new_options)

            # # # Compute 'Cash and cash equivalents, beginning of period'      (index=0)
            beginning_period_options = self._get_options_beginning_period(new_options)
            for account_id, account_code, account_name, balance in self._compute_liquidity_balance(beginning_period_options,
                                                                                                   currency_table_query,
                                                                                                   payment_account_ids):
                _insert_at_index(index_dict['line_begin'], account_id, account_code, account_name, balance, period)
                _insert_at_index(index_dict['line_end'], account_id, account_code, account_name, balance, period)

            # Compute 'Cash and cash equivalents, closing balance'          (index=16)
            for account_id, account_code, account_name, balance in self._compute_liquidity_balance(new_options,
                                                                                                   currency_table_query,
                                                                                                   payment_account_ids):
                _insert_at_index(index_dict['line_end'], account_id, account_code, account_name, balance, period)

            # ==== Process liquidity moves ====
            res = self._get_liquidity_move_report_lines(new_options, currency_table_query, payment_move_ids,
                                                        payment_account_ids)
            for account_id, account_code, account_name, account_internal_type, amount in res:
                _dispatch_result(account_id, account_code, account_name, account_internal_type, amount, period)

            # ==== Process reconciled moves ====
            res = self._get_reconciled_move_report_lines(new_options, currency_table_query, payment_move_ids,
                                                         payment_account_ids)
            for account_id, account_code, account_name, account_internal_type, balance in res:
                _dispatch_result(account_id, account_code, account_name, account_internal_type, balance, period)

            period += 1

        # Update Total amount for Line from its sub lines
        # In _insert_at_index, we only update total from account lines
        max_level = max(lines_to_compute, key=lambda x: x['level'])['level']
        while max_level > 0:
            current_level_lines = list(filter(lambda x: x['level'] == max_level, lines_to_compute))
            for line in current_level_lines:
                parent_id = line.get('parent_id', False)
                if parent_id:
                    parent_line = lines_to_compute[index_dict[parent_id]]
                    # Comparison Table
                    for period in range(no_of_periods):
                        amount = line['columns'][period]['name']
                        parent_line['columns'][period]['name'] += amount
            max_level -= 1

        # Net Cash & Difference
        for period in range(no_of_periods):
            net_line, _ = _get_amount_from_id('line_net', period)

            _, begin_amt = _get_amount_from_id('line_begin', period)
            _, end_amt = _get_amount_from_id('line_end', period)
            _, ar_amt = _get_amount_from_id('line_ar', period)
            _, ap_amt = _get_amount_from_id('line_ap', period)
            _, other_amt = _get_amount_from_id('line_other', period)

            # closing_ending_gap = end_amt - begin_amt
            computed_gap = ar_amt + ap_amt + other_amt
            for line_id in main_lines:
                _, amount = _get_amount_from_id(line_id, period)
                computed_gap += amount
            net_line['columns'][period]['name'] = computed_gap

            # delta = closing_ending_gap - computed_gap
            # if not self.env.user.company_id.currency_id.is_zero(delta):
            #     lines_to_compute.append({
            #         'id': 'cash_flow_line_unexplained_difference',
            #         'name': 'Unexplained Difference',
            #         'level': 0,
            #         'columns': [{'name': delta, 'class': 'number'}],
            #     })

        # *************************************************
        # ******************** DISPLAY ********************
        # *************************************************
        lines = []
        list_line_id = []  # to keep track of section line, we only display it once

        def _append_lines(current_line):
            if current_line['id'] not in list_line_id:
                # Display the current line
                for column in current_line['columns']:
                    amount = column['name']
                    if current_line.get('has_total_line', False):
                        column['class'] = 'number color-green' if amount > 0 else 'number color-red'
                    column['name'] = self.format_value(amount)
                lines.append(current_line)
                list_line_id.append(current_line['id'])

                # Check if it has children lines (account or sub lines)
                unfolded_lines = current_line.pop('unfolded_lines', {})
                sub_account_lines = [unfolded_lines[k] for k in sorted(unfolded_lines)]
                sub_lines = list(filter(lambda x: x.get('parent_id', False) == current_line['id'], lines_to_compute))

                current_line['unfoldable'] = len(sub_lines) > 0 or len(sub_account_lines) > 0
                current_line['unfolded'] = current_line['unfoldable'] and (
                        unfold_all or current_line['id'] in options['unfolded_lines'])

                # Display account & sub lines
                for sub_line in sub_account_lines:
                    for column in sub_line['columns']:
                        column['name'] = self.format_value(column['name'])
                    sub_line['style'] = '' if current_line['unfolded'] else 'display: none;'
                    lines.append(sub_line)

                for sub_line in sub_lines:
                    sub_line['style'] = '' if current_line['unfolded'] else 'display: none;'
                    _append_lines(sub_line)

                # Total line.
                if current_line.get('has_total_line', False):
                    lines.append({
                        'id': '{}_total'.format(current_line['id']),
                        'name': 'Total {}'.format(current_line['name']),
                        'level': current_line['level'] + 1,
                        'parent_id': current_line['id'],
                        'columns': [{**c, 'style': ''} for c in current_line['columns']],
                        'class': 'o_account_reports_domain_total',
                        'style': '' if current_line['unfolded'] else 'display: none;',
                    })

        for line in lines_to_compute:
            _append_lines(line)

        return lines
