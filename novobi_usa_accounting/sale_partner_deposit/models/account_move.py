# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        # Apply deposit from SO in Invoice
        res = super(AccountMove, self).action_post()

        for invoice in self:
            if invoice.type == 'out_invoice':
                sale_order_ids = self.env['sale.order']
                for line in invoice.invoice_line_ids:
                    sale_order_ids += line.sale_line_ids.mapped('order_id')
                deposits = sale_order_ids.mapped('deposit_ids')

                self._reconcile_deposit(deposits, invoice)
        return res
