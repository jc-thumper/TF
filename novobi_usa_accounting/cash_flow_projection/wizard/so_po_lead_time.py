# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LeadTimeSettings(models.TransientModel):
    _name = 'cash.flow.lead.time.setting'
    _description = 'Setting Lead Time for SO and PO'
    
    so_lead_time = fields.Integer(string='Due date for SO',
                                  default=lambda self: self.env.company.customer_payment_lead_time)
    po_lead_time = fields.Integer(string='Due date for PO',
                                  default=lambda self: self.env.company.vendor_payment_lead_time)
    
    def set_so_lead_time(self):
        self.ensure_one()
        if self.so_lead_time < 0 or self.po_lead_time < 0:
            raise ValidationError(_('Lead time should be greater than or equal to 0.'))
        self.env.company.customer_payment_lead_time = self.so_lead_time
        self.env.company.vendor_payment_lead_time = self.po_lead_time
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
