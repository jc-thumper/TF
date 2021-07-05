# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        # Apply deposit from PO in Invoice
        res = super(AccountMove, self).action_post()

        for invoice in self:
            if invoice.type == 'in_invoice':
                purchase_order_ids = invoice.invoice_line_ids.mapped('purchase_line_id.order_id')
                deposits = purchase_order_ids.mapped('deposit_ids')

                self._reconcile_deposit(deposits, invoice)
        return res
