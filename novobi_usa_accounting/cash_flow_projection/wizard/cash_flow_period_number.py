# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PeriodSettings(models.TransientModel):
    _name = 'cash.flow.period.setting'
    _description = 'Setting the number of period for Cashflow Projection'
    
    period_number = fields.Integer(string='Number of Periods',
                                   default=lambda self: self.env.company.cash_flow_period_number)
    
    def set_period_number(self):
        """
        Set the number of periods to show in the report
        @return: action to reload page
        """
        self.ensure_one()
        if self.period_number < 1 or self.period_number > 24:
            raise ValidationError(_('Please enter an integer between 1 and 24.'))
        self.env.company.cash_flow_period_number = self.period_number
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
