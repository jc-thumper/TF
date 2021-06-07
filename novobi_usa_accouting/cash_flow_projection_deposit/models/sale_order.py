# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2020 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import fields, models, api
from dateutil.relativedelta import relativedelta
import datetime


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    residual_deposit_amount = fields.Float(string='Residual Deposit Amount', default=0, required=True,
                                           compute='_compute_residual_deposit_amount', store=True)

    @api.depends('deposit_total', 'deposit_ids', 'deposit_ids.move_line_ids.amount_residual')
    def _compute_residual_deposit_amount(self):
        orders = self._filter_latest_order()
        for order in orders:
            order_sudo = order.sudo()
            deposit_ids = order_sudo.deposit_ids.filtered(lambda d: d.state not in ('draft', 'cancelled'))
            deposit_move_line_ids = [deposit_id.move_line_ids.filtered(lambda l: l.credit) for deposit_id in
                                     deposit_ids]
            order.residual_deposit_amount = sum(-line.amount_residual for line in deposit_move_line_ids)
    
    @api.depends('amount_total', 'invoice_ids', 'order_line.invoice_lines.move_id.state', 'residual_deposit_amount')
    def _get_remaining_so_amount(self):
        """
        Calculate the remaining amount of Sale Order
        @return:
        """
        orders = self._filter_latest_order()
        for order in orders:
            order_sudo = order.sudo()
            invoices = order_sudo.invoice_ids.filtered(
                lambda i: i.state not in ('draft', 'cancel') and i.type == 'out_invoice')
            total_invoice_amount = sum(invoices.mapped('amount_total'))
            order.update({
                'amount_so_remaining': order.amount_total - total_invoice_amount - order.residual_deposit_amount,
            })
    
    def _filter_latest_order(self):
        from_date = datetime.datetime.today() - relativedelta(months=2)
        if len(self) > 1:
            orders = self.filtered(lambda o: o.state == 'sale' and o.date_order and o.date_order > from_date)
        else:
            orders = self
        return orders
