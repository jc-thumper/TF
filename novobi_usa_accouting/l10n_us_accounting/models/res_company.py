# -*- coding: utf-8 -*-

from odoo import fields, models
from ..models.model_const import ACCOUNT_ACCOUNT


class ResCompany(models.Model):
    _inherit = "res.company"

    reconciliation_discrepancies_account_id = fields.Many2one('account.account', 'Reconciliation Discrepancies Account', domain=[('deprecated', '=', False)])
    bad_debt_account_id = fields.Many2one(ACCOUNT_ACCOUNT, string='Write Off Account',
                                          domain=[('deprecated', '=', False)])
