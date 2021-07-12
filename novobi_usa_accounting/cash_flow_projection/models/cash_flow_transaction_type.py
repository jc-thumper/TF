# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import api, fields, models, _


class CashFlowTransactionType(models.Model):
    _name = 'cash.flow.transaction.type'
    _description = 'Cash Flow Transaction Type'
    
    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    cash_type = fields.Selection(string='Cash Type', selection=[('none_cash', 'Cash Options'), ('cash_in', 'Cash In'),
                                                                ('cash_out', 'Cash Out')],
                                 required=True)
    is_show = fields.Boolean(string='Is Active?', default=True, required=True)
    editable = fields.Boolean(string='Is Editable?', default=False, required=True)
    sequence = fields.Integer(string='Sequence', default=0, required=True)
    
    _sql_constraints = [('unique_code', 'UNIQUE(code)', 'Transaction code must be unique')]
    
    @api.model
    def get_all_record(self):
        """
        Get the list of transaction type to show in the cash flow projection
        @return: the rendered list (included cash in and cash out) of the cash flow transaction
        """
        records = self.env['cash.flow.transaction.type'].sudo().search([])
        result = []
        for record in records:
            record_options = {
                'id': record.id,
                'name': record.name,
                'code': record.code,
                'cash_type': record.cash_type,
                'is_show': record.is_show,
                'editable': record.editable,
                'sequence': record.sequence,
            }
            result.append(record_options)
        cash_in_list = [r for r in result if r['cash_type'] == 'cash_in']
        cash_in_list.sort(key=lambda o: o['sequence'], reverse=False)
        cash_out_list = [r for r in result if r['cash_type'] == 'cash_out']
        cash_out_list.sort(key=lambda o: o['sequence'], reverse=False)
        none_cash_list = [r for r in result if r['cash_type'] == 'none_cash']
        none_cash_list.sort(key=lambda o: o['sequence'], reverse=False)
        show_past_due_transaction = False
        for transaction in none_cash_list:
            if transaction.get('code', '') == 'past_due_transaction' and transaction.get('is_show', False):
                show_past_due_transaction = True
                break
        return {
            'cash_in': cash_in_list,
            'cash_out': cash_out_list,
            'none_cash': none_cash_list,
            'show_past_due_transaction': show_past_due_transaction,
        }
    
    @api.model
    def set_active_transaction_type(self, record_id, code, state):
        """
        Update the user settings for showing/hiding a transaction type in the cash flow projection
        @param record_id: id of the specific transaction type
        @param code: code of the specific transaction type
        @param state: true for showing and false for hiding the transaction type
        @return:
        """
        record = self.env['cash.flow.transaction.type'].sudo().search([('id', '=', record_id), ('code', '=', code)])
        record.update({
            'is_show': state,
        })
    
    @api.model
    def is_editable(self, transaction_code):
        """
        Determine if a transaction type can be edited
        @param transaction_code: unique transaction code of the transaction type
        @return: Boolean value - True if can be edited
        """
        if not transaction_code:
            return False
        record = self.env['cash.flow.transaction.type'].sudo().search([('code', '=', transaction_code)])
        return record.editable and len(self.env.companies) < 2
