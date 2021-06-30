# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import api, fields, models, _


class CashFlowUserConfiguration(models.Model):
    _name = 'cash.flow.user.configuration'
    _description = 'Cash Flow User Configuration'
    
    period = fields.Char(string='Period', required=True)
    period_type = fields.Selection(string='Period Type',
                                   selection=[('day', 'Daily'), ('week', 'Weekly'), ('month', 'Monthly')],
                                   required=True)
    cash_type = fields.Selection(string='Cash Type', selection=[('cash_in', 'Cash In'), ('cash_out', 'Cash Out')],
                                 required=True)
    transaction_type = fields.Many2one('cash.flow.transaction.type', string='Transaction Type', required=True)
    value = fields.Float(string='Value', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id)
    
    @api.model
    def get_recurring_value(self, period_type, cash_type):
        record = self.env['cash.flow.user.configuration'].sudo().search(
            [('cash_type', '=', cash_type), ('period_type', '=', period_type),
             ('period', '=', period_type), ('company_id', '=', self.env.user.company_id.id)])
        return record and record.value or 0.0
