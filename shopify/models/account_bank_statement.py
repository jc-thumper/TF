# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class BankStatement(models.Model):
    _inherit = 'account.bank.statement'

    shopify_ref = fields.Char("Shopify Reference")


class BankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    shopify_order_id = fields.Many2one("sale.order", copy=False)
