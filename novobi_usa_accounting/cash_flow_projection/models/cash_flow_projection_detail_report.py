# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import models, fields, api, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json


class CashflowDetailReport(models.AbstractModel):
    _name = "account.cash.flow.report.detail"
    _description = "Cash Flow Report"
    _inherit = "account.report"
    
    # filter_unfold_all = True
    # filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_month'}
    filter_multi_company = None
    
    def _get_columns_name(self, options):
        columns = [{'name': ''}, {'name': 'Payment Date/Due date', 'class': 'date'},
                   {'name': 'Customer/Partner'}, {'name': 'Amount'}]
        return columns
    
    def _get_templates(self):
        templates = super(CashflowDetailReport, self)._get_templates()
        templates['main_template'] = 'account_reports.main_template'
        try:
            self.env['ir.ui.view'].get_view_id('cash_flow_projection.line_template_cash_flow_detail')
            templates['line_template'] = 'cash_flow_projection.line_template_cash_flow_detail'
        except ValueError:
            pass
        return templates
    
    @api.model
    def _resolve_caret_option_view(self, target):
        res = super(CashflowDetailReport, self)._resolve_caret_option_view(target)
        if target._name == 'sale.order':
            res = 'sale.view_order_form'
        if target._name == 'purchase.order':
            res = 'purchase.purchase_order_form'
        return res
    
    def open_journal_items(self, options, params):
        # Pop the financial_group_line_id for the caret options to show the account move line
        if params.get('financial_group_line_id'):
            params.pop('financial_group_line_id')
        return super(CashflowDetailReport, self).open_journal_items(options, params)
    
    def print_xlsx(self, options):
        ctx_period_name = self.env.context.get('period_name')
        period_type = self.env.context.get('period_type')
        ctx_code = self.env.context.get('transaction_code')
        opening_balance = self.env.context.get('opening_balance')
        forward_balance = self.env.context.get('forward_balance')
        options.update({
            'period_name': ctx_period_name,
            'period_type': period_type,
            'transaction_code': ctx_code,
            'opening_balance': opening_balance,
            'forward_balance': forward_balance,
        })
        return {
            'type': 'ir_actions_account_report_download',
            'data': {'model': self.env.context.get('model'),
                     'options': json.dumps(options),
                     'output_format': 'xlsx',
                     'financial_id': self.env.context.get('id'),
                     }
        }
    
    @api.model
    def _get_lines(self, options, line_id=None):
        ctx_code = self.env.context.get('transaction_code') or options.get('transaction_code')
        ctx_opening_balance = self.env.context.get('opening_balance') or options.get('opening_balance') or 0
        ctx_forward_balance = self.env.context.get('forward_balance') or options.get('forward_balance') or 0
        
        if ctx_code == 'detail':
            ctx_code = ''
        
        if ctx_code:
            transaction_type = self.env['cash.flow.transaction.type'].search([('code', '=', ctx_code)])[0]
            list_in = list_out = [{
                'id': transaction_type.id,
                'name': transaction_type.name,
                'code': transaction_type.code,
                'cash_type': transaction_type.cash_type,
                'is_show': transaction_type.is_show,
                'editable': transaction_type.editable,
                'sequence': transaction_type.sequence,
            }]
        else:
            list_transaction_type = self.env['cash.flow.transaction.type'].get_all_record()
            list_in = list_transaction_type.get('cash_in') or []
            list_out = list_transaction_type.get('cash_out') or []
        lines = []
        if not ctx_code:
            # Opening balance
            opening_balance = {
                'id': 'opening_balance',
                'name': _('Current Cash & Bank Balance'),
                'level': 0,
                'unfoldable': False,
                'class': 'total',
                'columns': [{'name': '', 'class': 'date'},
                            {'name': ''}, {'name': self.format_value(ctx_opening_balance), 'class': 'number'}]
            }
            lines.append(opening_balance)
            forward_balance = {
                'id': 'forward_balance',
                'name': _('Balance Brought Forward'),
                'level': 0,
                'unfoldable': False,
                'class': 'total',
                'columns': [{'name': '', 'class': 'date'},
                            {'name': ''}, {'name': self.format_value(ctx_forward_balance), 'class': 'number'}]
            }
            lines.append(forward_balance)
            # Cash In
            in_lines, total_cash_in = self.render_cash_in_out_lines(list_in, options)
            cash_in_line = {
                'id': 'cash_in',
                'name': _('Cash In'),
                'level': 0,
                'unfoldable': False,
                'class': 'total',
                'columns': [{'name': '', 'class': 'date'},
                            {'name': ''}, {'name': '', 'class': 'number'}]
            }
            lines.append(cash_in_line)
            lines = lines + in_lines
            # Total Cash In
            total_cash_in_line = {
                'id': 'total_cash_in',
                'name': _('Total Cash In'),
                'level': 0,
                'unfoldable': False,
                'class': 'total',
                'columns': [{'name': '', 'class': 'date'},
                            {'name': ''}, {'name': self.format_value(total_cash_in), 'class': 'number'}]
            }
            lines.append(total_cash_in_line)
        # Cash Out
        out_lines, total_cash_out = self.render_cash_in_out_lines(list_out, options)
        cash_out_line = {
            'id': 'cash_out',
            'name': _('Cash Out'),
            'level': 0,
            'unfoldable': False,
            'class': 'total',
            'columns': [{'name': '', 'class': 'date'},
                        {'name': ''}, {'name': '', 'class': 'number'}]
        }
        if not ctx_code:
            lines.append(cash_out_line)
        lines = lines + out_lines
        if not ctx_code:
            # Total Cash Out
            total_cash_out_line = {
                'id': 'total_cash_out',
                'name': _('Total Cash Out'),
                'level': 0,
                'unfoldable': False,
                'class': 'total',
                'columns': [{'name': '', 'class': 'date'},
                            {'name': ''}, {'name': self.format_value(total_cash_out), 'class': 'number'}]
            }
            lines.append(total_cash_out_line)
            # Net increase balance
            net_cash_line = {
                'id': 'net_cash',
                'name': _('Net Cashflow/Balance Carried Forward'),
                'level': 0,
                'unfoldable': False,
                'class': 'total',
                'columns': [{'name': '', 'class': 'date'},
                            {'name': ''},
                            {'name': self.format_value(
                                round(ctx_opening_balance + ctx_forward_balance + total_cash_in - total_cash_out, 2)),
                                'class': 'number'}]
            }
            lines.append(net_cash_line)
        return lines
    
    def render_cash_in_out_lines(self, list_transaction, options):
        lines = []
        total_cash_change = 0.0
        for transaction in list_transaction:
            if transaction.get('is_show'):
                parent_id = transaction.get('code')
                sub_lines, caret_options = self.get_transaction(parent_id, options)
                sub_lines_filtered = [l for l in sub_lines if l['id'] == parent_id]
                total_amount = sum(line['amount'] for line in sub_lines_filtered)
                total_cash_change += total_amount
                parent_line = {
                    'id': parent_id,
                    'name': transaction.get('name'),
                    'unfoldable': True,
                    'unfolded': True,
                    'level': 2,
                    # 'class': 'total',
                    'columns': [{'name': '', 'class': 'date'},
                                {'name': ''}, {'name': self.format_value(round(total_amount, 2)), 'class': 'number'}]
                }
                lines.append(parent_line)
                for sub_line in sub_lines_filtered:
                    lines.append({
                        'id': sub_line.get('line_id'),
                        'name': sub_line.get('account_name'),
                        'level': 4,
                        'parent_id': parent_id,
                        'caret_options': caret_options,
                        # 'unfoldable': False,
                        'columns': [{'name': sub_line.get('date'), 'class': 'date'},
                                    {'name': sub_line.get('partner_name')},
                                    {'name': self.format_value(sub_line['amount']), 'class': 'number'}]
                    })
        return lines, round(total_cash_change, 2)
    
    def _get_report_name(self):
        ctx_period_name = self.env.context.get('period_name')
        if ctx_period_name:
            if ctx_period_name == 'Past Due Transactions':
                return _('Cashflow Forecast - Detail Past Due Transactions')
            return _('Cashflow Forecast - Detail Report for Period: {}'.format(ctx_period_name))
        return _('Cashflow Forecast - Detail Report')
    
    def get_date_from_string(self, dateString, options):
        from_date = datetime.today()
        to_date = datetime.today()
        if dateString == 'Past Due Transactions':
            period_unit = self.env.context.get('period_type') or options.get('period_type')
            week_spacing = month_spacing = 0
            if period_unit == 'week':
                week_spacing = 1
            elif period_unit == 'month':
                month_spacing = 1
            # Calculate the start day and end date of the cycle
            weekday = (to_date.weekday() + 1) % 7
            start_date = to_date - relativedelta(days=(weekday * week_spacing + (to_date.day - 1) * month_spacing))
            to_date = start_date - relativedelta(days=1)
            from_date = to_date - relativedelta(months=1)
        elif dateString:
            if '-' in dateString:
                index = dateString.index('-')
                from_date = datetime.strptime(dateString[:index], '%m/%d/%y')
                to_date = datetime.strptime(dateString[index + 1:], '%m/%d/%y')
            elif '/' in dateString:
                from_date = datetime.strptime(dateString, '%m/%d/%y')
                to_date = datetime.strptime(dateString, '%m/%d/%y')
            else:
                index = dateString.index(' ')
                month = dateString[:index]
                year = dateString[index + 1:]
                from_date = datetime.strptime('{}/01/{}'.format(month, year), '%b/%d/%Y')
                to_date = from_date + relativedelta(months=1, days=-1)
                from_date, to_date = from_date, to_date
        return datetime.date(from_date), datetime.date(to_date)
    
    def get_transaction(self, transaction_code, options):
        cfp = self.env['cash.flow.projection'].create({})
        query = ''
        caret_options = 'account.move'
        should_return_details = True
        value = 0
        account_name = 'Others'
        ctx_period_name = self.env.context.get('period_name') or options.get('period_name')
        period_type = self.env.context.get('period_type') or options.get('period_type')
        date_from, date_to = self.get_date_from_string(ctx_period_name, options)
        
        if transaction_code == 'future_customer_payment':
            query = cfp._query_incoming_payment_lines(date_from, date_to)
        elif transaction_code == 'sale_order':
            caret_options = 'sale.order'
            query = cfp._query_so_lines(date_from, date_to)
        elif transaction_code == 'ar_credit_note':
            query = cfp._query_ar_credit_note_lines(date_from, date_to)
        elif transaction_code == 'ar_invoice':
            query = cfp._query_ar_invoice_lines(date_from, date_to)
        elif transaction_code == 'cash_in_other':
            show_past_due_transaction = ctx_period_name and ctx_period_name == 'Past Due Transactions' or False
            if ctx_period_name and period_type:
                value = cfp._get_user_value(ctx_period_name, period_type, 'cash_in', transaction_code,
                                            show_past_due_transaction)
                account_name = 'Recurring Cash In'
            query = cfp._query_other_cash_in_lines(date_from, date_to)
            should_return_details = False
            caret_options = ''
        elif transaction_code == 'future_vendor_payment':
            query = cfp._query_outgoing_payment_lines(date_from, date_to)
        elif transaction_code == 'purchase_order':
            caret_options = 'purchase.order'
            query = cfp._query_po_lines(date_from, date_to)
        elif transaction_code == 'ap_credit_note':
            query = cfp._query_ap_credit_note_lines(date_from, date_to)
        elif transaction_code == 'ap_invoice':
            query = cfp._query_ap_invoice_lines(date_from, date_to)
        elif transaction_code == 'cash_out_other':
            if ctx_period_name and period_type:
                show_past_due_transaction = ctx_period_name and ctx_period_name == 'Past Due Transactions' or False
                value = cfp._get_user_value(ctx_period_name, period_type, 'cash_out', transaction_code,
                                            show_past_due_transaction)
                account_name = 'Recurring Cash Out'
            query = cfp._query_other_cash_out_lines(date_from, date_to)
            should_return_details = False
            caret_options = ''
        query = query + ' ORDER BY date ASC'
        self.env.cr.execute(query)
        detail_transaction = self.env.cr.dictfetchall()
        if should_return_details:
            return detail_transaction, caret_options
        else:
            for transaction in detail_transaction:
                if account_name:
                    transaction['account_name'] = account_name
                if value:
                    transaction['amount'] = value
            return detail_transaction, caret_options
