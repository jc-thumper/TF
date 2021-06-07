# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import fields, models, api
from dateutil.relativedelta import relativedelta
import datetime


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    amount_so_remaining = fields.Monetary(string='Unpaid Amount', default=0,
                                          compute="_get_remaining_so_amount", store=True)
    
    @api.depends('amount_total', 'invoice_ids', 'order_line.invoice_lines.move_id.state')
    def _get_remaining_so_amount(self):
        """
        Calculate the remaining amount of Purchase Order
        @return:
        """
        from_date = datetime.datetime.today() - relativedelta(months=2)
        if len(self) > 1:
            orders = self.filtered(
                lambda o: o.state == 'purchase' and ((o.date_approve and o.date_approve > from_date) or (
                        not o.date_approve and o.date_order and o.date_order > from_date)))
        else:
            orders = self
        for order in orders:
            order_sudo = order.sudo()
            invoices = order_sudo.invoice_ids.filtered(
                lambda i: i.state not in ('draft', 'cancel') and i.type == 'in_invoice')
            total_invoice_amount = sum(invoices.mapped('amount_total'))
            order.update({
                'amount_so_remaining': order.amount_total - total_invoice_amount,
            })
