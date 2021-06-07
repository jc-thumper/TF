# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'
    
    account_eligible_1099 = fields.Boolean('Eligible for 1099?', default=False)
