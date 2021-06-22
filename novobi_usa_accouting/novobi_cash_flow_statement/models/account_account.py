# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AccountAccount(models.Model):
    _inherit = 'account.account'

    cashflow_structure_line_id = fields.Many2one('cash.flow.report.structure.line',
                                                 string='Cashflow Statement Group')
