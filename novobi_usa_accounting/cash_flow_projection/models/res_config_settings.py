# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    customer_payment_lead_time = fields.Integer(related='company_id.customer_payment_lead_time',
                                                string='Due date for SO', readonly=False)
    vendor_payment_lead_time = fields.Integer(related='company_id.vendor_payment_lead_time',
                                              string='Due date for PO', readonly=False)
    cash_flow_period_number = fields.Integer(related='company_id.cash_flow_period_number', string='Number of period',
                                             readonly=False)
    module_cash_flow_projection_deposit = fields.Boolean("Deposits for Cash Flow Projection")
