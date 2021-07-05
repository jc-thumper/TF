# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import api, fields, models, _


class PeriodSettings(models.TransientModel):
    _name = 'cash.flow.recurring.setting'
    _description = 'Setting the number of period for Cashflow Projection'
    
    amount = fields.Float(string='Cash Amount', default=0)
    period_type = fields.Selection(string='Period Type',
                                   selection=[('day', 'day'), ('week', 'week'), ('month', 'month')],
                                   default='month', required=True)
    cash_type = fields.Selection(string='Cash Type', selection=[('cash_in', 'Cash In'), ('cash_out', 'Cash Out')])
    
    def set_recurring_cash_in(self):
        self.ensure_one()
        self.cash_type = self.env.context.get('cash_type')
        # self.period_type = self.env.context.get('period_type')
        if not self.cash_type:
            return
        code = self.cash_type == 'cash_in' and 'cash_in_other' or 'cash_out_other'
        transaction_type = self.env['cash.flow.transaction.type'].sudo().search([('code', '=', code)])
        if not transaction_type:
            return
        record = self.env['cash.flow.user.configuration'].sudo().search(
            [('cash_type', '=', self.cash_type), ('period_type', '=', self.period_type),
             ('transaction_type', '=', transaction_type.id),
             ('period', '=', self.period_type), ('company_id', '=', self.env.user.company_id.id)])
        if not record:
            vals = {
                'period': self.period_type,
                'period_type': self.period_type,
                'cash_type': self.cash_type,
                'transaction_type': transaction_type.id,
                'value': self.amount,
                'company_id': self.env.user.company_id.id,
            }
            record = self.env['cash.flow.user.configuration'].sudo().create(vals)
        else:
            record.value = self.amount
        # Remove all existing records
        existing_records = self.env['cash.flow.user.configuration'].sudo().search(
            [('cash_type', '=', self.cash_type), ('period_type', '=', self.period_type),
             ('transaction_type', '=', transaction_type.id), ('id', '!=', record.id),
             ('company_id', '=', self.env.user.company_id.id)])
        for exsiting_record in existing_records:
            exsiting_record.unlink()
        # Reload page
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
