# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    is_validate_invoice = fields.Boolean('Validate invoice after creation?',
                                         help='Check this if you want to validate the invoice. '
                                              'Otherwise it will be in draft.')
    # Override
    @api.model
    def _get_advance_payment_method(self):
        return 'delivered'

    def create_invoices(self):
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

        if self.advance_payment_method in ['delivered', 'all'] and self.is_validate_invoice:
            sale_orders.with_context(validate_invoice=True)._create_invoices()

            if self._context.get('open_invoices', False):
                return sale_orders.action_view_invoice()
            return {'type': 'ir.actions.act_window_close'}
        else:
            return super(SaleAdvancePaymentInv, self).create_invoices()
