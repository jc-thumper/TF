# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PaymentDeposit(models.Model):
    _inherit = 'account.payment'

    purchase_deposit_id = fields.Many2one('purchase.order', 'Purchase Order',
                                          help='Is this deposit made for a particular Purchase Order?')

    @api.onchange('partner_id')
    def _onchange_partner_purchase_id(self):
        if self.payment_type == 'outbound':
            return self._onchange_partner_order_id('purchase_deposit_id', ['purchase'])

    def post(self):
        # Check one last time before Validate. Not gonna happen.
        self._validate_order_id('purchase_deposit_id', 'Purchase Order')
        return super(PaymentDeposit, self).post()
