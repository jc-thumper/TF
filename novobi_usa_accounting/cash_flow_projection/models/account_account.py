# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import api, fields, models


class Account(models.Model):
    _inherit = 'account.account'
    
    payment_lead_time = fields.Integer(string='Payment Lead Time', default=0)
