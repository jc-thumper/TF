# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from ...l10n_custom_dashboard.utils.graph_setting import get_chartjs_setting, get_linechart_format, get_barchart_format, get_chart_json
from ..utils.graph_utils import get_json_data_for_selection, get_json_render, get_chart_point_name, \
    append_data_fetch_to_list
from ..models.usa_journal import CUSTOMER_INVOICE, VENDOR_BILLS, COLOR_PAID_INVOICE, COLOR_OPEN_INVOICES, \
    COLOR_OPEN_BILLS, COLOR_PAID_BILLS, COLOR_BANK, COLOR_BOOK
from ..utils.utils import get_list_companies_child
from ..utils.time_utils import BY_MONTH, BY_QUARTER, BY_FISCAL_YEAR, get_list_period_by_type
from ..models.usa_journal import COLOR_VALIDATION_DATA, PRIMARY_BLUE
from odoo import models, api, _, fields
from odoo.tools.misc import formatLang
from datetime import datetime

LIGHTER_BLUE = '#8ebaf5'


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _kanban_dashboard_graph(self):
        for record in self:
            journal_type = record.type
            kanban_dashboard_graph = False

            if journal_type in ['sale', 'purchase']:
                type_data = "bar"
                extend_mode, graph_data = record.get_general_kanban_section_data()
                selection = []
                get_json_data_for_selection(record, selection, record.period_by_month, record.default_period_by_month)
                function_retrieve = 'retrieve_account_invoice'
                extra_param = [journal_type, record.id]
                kanban_dashboard_graph = json.dumps(get_json_render(type_data, False, '', graph_data, journal_type, selection, function_retrieve, extra_param))

            elif journal_type in ['cash', 'bank']:
                type_data = "line"
                data = record.get_line_graph_datas()
                record.format_graph_data_of_bank(data)
                selection = []
                function_retrieve = ''
                extra_param = []

                labels = list(map(lambda item: item['x'], data[0]['values'])) if len(data) else []
                graph_data = []
                for line in data:
                    value = list(map(lambda item: item['y'], line['values']))
                    graph_data.append(get_linechart_format(data=value, label=line['key'], color=PRIMARY_BLUE,
                                                           background_color=LIGHTER_BLUE, fill=True))

                # data_type, extend, data_render, name_card, selection, function_retrieve)
                kanban_dashboard_graph = json.dumps(get_json_render(type_data, False, labels, graph_data, journal_type, selection, function_retrieve, extra_param))

            record.kanban_dashboard_graph = kanban_dashboard_graph

    def _kanban_right_info_graph(self):
        for record in self:
            journal_type = record.type
            if journal_type in ['bank']:
                labels = []
                graph_data = [
                    get_barchart_format([record.get_balance_per_book()], _('Balance per Book'), COLOR_BOOK),
                    get_barchart_format([record.get_balance_per_bank()], _('Balance per Bank'), COLOR_BANK),
                ]
                selection = []
                function_retrieve = ''
                extra_param = []
                setting = get_chartjs_setting(chart_type='horizontalBar', horizontal=True)
                record.kanban_right_info_graph = json.dumps(
                    get_json_render('horizontalBar', False, labels, graph_data, journal_type, selection, function_retrieve, extra_param, setting))
            else:
                record.kanban_right_info_graph = ''

    period_by_month = [{'n': 'This Month', 'd': 0, 't': BY_MONTH},
                       {'n': 'This Quarter', 'd': 0, 't': BY_QUARTER},
                       {'n': 'This Fiscal Year', 'd': 0, 't': BY_FISCAL_YEAR},
                       {'n': 'Last Month', 'd': -1, 't': BY_MONTH},
                       {'n': 'Last Quarter', 'd': -1, 't': BY_QUARTER},
                       {'n': 'Last Fiscal Year', 'd': -1, 't': BY_FISCAL_YEAR}, ]
    default_period_by_month = 'This Fiscal Year'
    kanban_right_info_graph = fields.Text(compute='_kanban_right_info_graph')

    def get_general_kanban_section_data(self):
        data = []

        (graph_title, graph_key) = ('', '')
        extend_data = False
        return extend_data, [{
            'values': data,
            'title': graph_title,
            'key': graph_key,
            'color': COLOR_VALIDATION_DATA}]

    @api.model
    def retrieve_account_invoice(self, date_from, date_to, period_type=BY_MONTH, type_invoice=VENDOR_BILLS, journal_id=None):
        """ API is used to response total amount of open/paid account invoice
        and any info relate to show in "Customer Invoices" and "Vendor Bills"
        kanban sections.

        :param date_from: the start date to summarize data, have type is datetime
        :param date_to: the end date to summarize data, that have type is datetime
        :param period_type: is type of period to summarize data, we have 4 selections are
                ['week', 'month', 'quarter', 'year']
        :param type_invoice: two case is out_invoice for "Customer Invoices" and in_invoice in "Vendor Bills"
        :param journal_id: id of this journal.
        :return: Json
                {
                    'graph_data': [{json to render graph data}]
                    'info_data': [{'name': 'the label will show for summarize data', 'summarize': 'summarize data'}]
                }
        """
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
        date_to = datetime.strptime(date_to, '%Y-%m-%d')
        periods = get_list_period_by_type(self, date_from, date_to, period_type)

        type_invoice_select = 'in_invoice' if type_invoice == VENDOR_BILLS else 'out_invoice'

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
            SELECT ai.journal_id,
                ai.invoice_date,
                c.rate * (CASE WHEN type IN ('out_refund', 'in_refund') THEN -1 ELSE 1 END) * ai.amount_residual AS amount_residual_tran,
                c.rate * (CASE WHEN type IN ('out_refund', 'in_refund') THEN -1 ELSE 1 END) * ai.amount_total AS amount_total_tran,
                state, type, company_id
            FROM account_move AS ai
                LEFT JOIN ({currency_table}) AS c ON ai.currency_id = c.id
        """.format(currency_table=currency)

        journal = 'aic.journal_id = {} AND'.format(journal_id) if journal_id else ''

        query = """
            SELECT date_part('year', aic.invoice_date::DATE) AS year,
                date_part(%s, aic.invoice_date::DATE) AS period,
                COUNT(*),
                MIN(aic.invoice_date) AS date_in_period,
                SUM(aic.amount_total_tran) AS total,
                SUM(aic.amount_residual_tran) AS amount_due
            FROM ({transferred_currency}) AS aic
            WHERE aic.invoice_date >= %s AND 
                aic.invoice_date <= %s AND
                aic.state = 'posted' AND
                aic.type = %s AND
                {journal}
                aic.company_id IN %s
            GROUP BY year, period
            ORDER BY year, period;
        """.format(transferred_currency=transferred_currency, journal=journal)

        company_ids = get_list_companies_child(self.env.company)
        name = fields.Date.today()
        self.env.cr.execute(query, (period_type, name, tuple(company_ids), date_from, date_to, type_invoice_select, tuple(company_ids),))
        data_fetch = self.env.cr.dictfetchall()

        data_list = [[], []]
        graph_label = []
        index = 0

        for data in data_fetch:
            while not (periods[index][0] <= data['date_in_period'] <= periods[index][1]) and index < len(periods):
                append_data_fetch_to_list(data_list, graph_label, periods, period_type, index)
                index += 1
            if index < len(periods):
                values = [data['amount_due'], data['total'] - data['amount_due']]
                append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=values)
                index += 1

        while index < len(periods):
            append_data_fetch_to_list(data_list, graph_label, periods, period_type, index)
            index += 1

        if type_invoice == CUSTOMER_INVOICE:
            label = 'Invoices'
            color = [COLOR_OPEN_INVOICES, COLOR_PAID_INVOICE]
        else:
            label = 'Bills'
            color = [COLOR_OPEN_BILLS, COLOR_PAID_BILLS]

        graph_data = [
            get_barchart_format(data_list[0], _('Unpaid ' + label), color[0]),
            get_barchart_format(data_list[1], _('Paid ' + label), color[1]),
        ]

        return get_chart_json(graph_data, graph_label, get_chartjs_setting(chart_type='bar', mode='index', stacked=True))

    def get_balance_per_book(self):
        self.ensure_one()
        account_sum = 0
        if self.type in ['bank', 'cash']:
            # Get the number of items to reconcile for that bank journal
            query = """
                SELECT COUNT(DISTINCT(line.id))
                FROM account_bank_statement_line AS line
                    LEFT JOIN account_bank_statement AS st ON line.statement_id = st.id
                WHERE st.journal_id IN %s AND
                    st.state = 'open' AND
                    line.amount != 0.0 AND
                    line.account_id IS NULL AND
                    NOT EXISTS (SELECT 1 FROM account_move_line aml WHERE aml.statement_line_id = line.id)
            """
            self.env.cr.execute(query, (tuple(self.ids),))

            # optimization to read sum of balance from account_move_line
            account_ids = tuple(
                ac for ac in [self.default_debit_account_id.id, self.default_credit_account_id.id] if ac)
            if account_ids:
                amount_field = 'aml.balance' if (not self.currency_id or self.currency_id == self.company_id.currency_id) else 'aml.amount_currency'
                query = """
                    SELECT sum(%s)
                    FROM account_move_line aml LEFT JOIN account_move move ON aml.move_id = move.id
                    WHERE aml.account_id in %%s AND move.date <= %%s AND move.state = 'posted';
                """ % (amount_field,)
                self.env.cr.execute(query, (account_ids, fields.Date.today(),))
                query_results = self.env.cr.dictfetchall()

                if query_results and query_results[0].get('sum') is not None:
                    account_sum = query_results[0].get('sum')
        return account_sum

    def get_balance_per_bank(self):
        self.ensure_one()
        last_balance = 0
        if self.type in ['bank', 'cash']:
            last_bank_stmt = self.env['account.bank.statement'].search([('journal_id', 'in', self.ids)], order="date desc, id desc", limit=1)
            last_balance = last_bank_stmt and last_bank_stmt[0].balance_end or 0
        return last_balance

    ########################################################
    # GENERAL FUNCTIONS
    ########################################################
    def _get_tuple_type(self):
        tuple_type = None
        if self.type == 'sale':
            tuple_type = tuple(['out_invoice'])
        elif self.type == 'purchase':
            tuple_type = tuple(['in_invoice'])
        return tuple_type

    def format_graph_data_of_bank(self, graph_data):
        for item in graph_data:
            item['key'] = item.get('key', '').replace(':', '')
            last_item = item.get('values')[-1]
            if last_item:
                last_item['x'] = 'Now'

            # change the color of line and also area of graph
            item['color'] = PRIMARY_BLUE

    def _get_bills_aging_range_time_query(self, tuple_type, lower_bound_range=None, upper_bound_range=None):
        """
        Returns a tuple containing as its first element the SQL query used to
        gather the bills in open state data, aging date in range and the arguments
        dictionary to use to run it as its second.
        """
        lower_bound_condition = 'AND aging_days >= {}'.format(lower_bound_range) if isinstance(lower_bound_range, int) else ''
        upper_bound_condition = 'AND aging_days <= {}'.format(upper_bound_range) if isinstance(upper_bound_range, int) else ''
        query = """
            SELECT invoice_payment_state,
                amount_total,
                (CASE WHEN type IN ('out_refund', 'in_refund') THEN -1 ELSE 1 END) * amount_residual AS amount_residual,
                currency_id AS currency,
                type,
                invoice_date,
                company_id
            FROM account_move
            WHERE journal_id = %(journal_id)s AND
                type in %(tuple_type)s AND
                invoice_payment_state = 'not_paid' AND
                state = 'posted'
                {lower_bound_condition} {upper_bound_condition};
        """.format(lower_bound_condition=lower_bound_condition, upper_bound_condition=upper_bound_condition)

        return query, {'journal_id': self.id, 'tuple_type': tuple_type}

    def _get_draft_bills_query(self):
        """
        Returns a tuple containing as its first element the SQL query used to
        gather the bills in draft state data, and the arguments
        dictionary to use to run it as its second.
                """
        old_query, query_args = super(AccountJournal, self)._get_draft_bills_query()

        query = """
            SELECT *
            FROM ({old_query}) as temp
            WHERE type in %(type)s;
        """.format(old_query=old_query.replace(';', ''))
        query_args.update({'type': self._get_tuple_type()})
        return query, query_args

    def _count_results_and_sum_residual_signed(self, results_dict, target_currency):
        """ Loops on a query result to count the total number of invoices and sum
        their amount_total field (expressed in the given target currency).
        """
        rslt_count = 0
        rslt_sum = 0.0
        for result in results_dict:
            cur = self.env['res.currency'].browse(result.get('currency'))
            company = self.env['res.company'].browse(result.get('company_id')) or self.env.company
            rslt_count += 1
            type_factor = result.get('type') in ('in_refund', 'out_refund') and -1 or 1
            rslt_sum += type_factor * cur._convert(
                result.get('amount_residual'), target_currency, company,
                result.get('invoice_date') or fields.Date.today())
        return rslt_count, rslt_sum

    def get_journal_dashboard_datas(self):
        datas = super(AccountJournal, self).get_journal_dashboard_datas()
        currency = self.currency_id or self.company_id.currency_id
        if self.type == 'bank':
            datas.update({
                'is_credit_card': self.is_credit_card,
            })
            if self.is_credit_card:
                datas.update({
                    'unpaid_balance_statement': formatLang(self.env, currency.round(self.partner_id.debit) + 0.0,
                                                           currency_obj=currency),
                })
        elif self.type in ['sale', 'purchase']:
            tuple_type = self._get_tuple_type()

            (query, query_args) = self._get_bills_aging_range_time_query(tuple_type, lower_bound_range=0)
            self.env.cr.execute(query, query_args)
            query_results_open_invoices = self.env.cr.dictfetchall()

            (query, query_args) = self._get_bills_aging_range_time_query(tuple_type, lower_bound_range=1, upper_bound_range=30)
            self.env.cr.execute(query, query_args)
            query_results_in_month = self.env.cr.dictfetchall()

            (query, query_args) = self._get_bills_aging_range_time_query(tuple_type, lower_bound_range=31)
            self.env.cr.execute(query, query_args)
            query_results_over_month = self.env.cr.dictfetchall()

            (number_open_invoices, sum_open_invoices) = self._count_results_and_sum_residual_signed(query_results_open_invoices, currency)
            (number_in_month, sum_in_month) = self._count_results_and_sum_residual_signed(query_results_in_month, currency)
            (number_over_month, sum_over_month) = self._count_results_and_sum_residual_signed(query_results_over_month, currency)

            datas.update({
                'number_open_invoices': number_open_invoices,
                'sum_open_invoices': formatLang(self.env, currency.round(sum_open_invoices) + 0.0, currency_obj=currency),
                'number_in_month': number_in_month,
                'sum_in_month': formatLang(self.env, currency.round(sum_in_month) + 0.0, currency_obj=currency),
                'number_over_month': number_over_month,
                'sum_over_month': formatLang(self.env, currency.round(sum_over_month) + 0.0, currency_obj=currency),
                # 'number_draft': number_draft,
                # 'sum_draft': formatLang(self.env, currency.round(sum_draft) + 0.0, currency_obj=currency),
            })
        return datas

    def open_action(self):
        domain = self._context.get('use_domain', [])
        action = super(AccountJournal, self).open_action()
        # remove any domain related to field type
        if isinstance(action['domain'], list):
            action['domain'] = [cond for cond in action['domain'] if cond[0] != 'type']
        else:
            action['domain'] = []
        # append new domain related to any customs domain of dev passed from file xml
        action['domain'] += domain

        # append new domain related to filed type
        if not self._context.get('invoice_type', False):
            if self.type == 'sale':
                action['domain'].append(('type', 'in', ['out_invoice']))
            elif self.type == 'purchase':
                action['domain'].append(('type', 'in', ['in_invoice']))

        action['domain'].append(('journal_id', '=', self.id))

        return action

    ########################################################
    # INITIAL DATA
    ########################################################
    @api.model
    def change_status_favorite(self):
        cashes = self.search([('type', '=', 'cash')])
        for cash in cashes:
            cash.write({'show_on_dashboard': False})
