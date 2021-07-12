# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class Partner(models.Model):
    _inherit = 'res.partner'

    property_account_customer_deposit_id = fields.Many2one('account.account', company_dependent=True,
                                                           string="Customer Deposit Account",
                                                           domain=lambda self: [('user_type_id', 'in', [self.env.ref(
                                                               'account.data_account_type_current_liabilities').id]),
                                                                                ('deprecated', '=', False),
                                                                                ('reconcile', '=', True)])

    property_account_vendor_deposit_id = fields.Many2one('account.account', company_dependent=True,
                                                         string="Vendor Deposit Account",
                                                         domain=lambda self: [('user_type_id', 'in', [self.env.ref(
                                                             'account.data_account_type_prepayments').id]),
                                                                              ('deprecated', '=', False),
                                                                              ('reconcile', '=', True)])

    customer_deposit_aml_ids = fields.One2many('account.move.line', 'partner_id',
                                               domain=[('payment_id.is_deposit', '=', True),
                                                       ('payment_id.payment_type', '=', 'inbound'), # Only customer deposit
                                                       ('reconciled', '=', False),
                                                       ('credit', '>', 0), ('debit', '=', 0),
                                                       '|', ('amount_residual', '!=', 0.0),
                                                       ('amount_residual_currency', '!=', 0.0)])

