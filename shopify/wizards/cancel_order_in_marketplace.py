from .. import shopify
from datetime import datetime
from odoo import models, api, fields, _
from odoo.addons import decimal_precision as dp
from odoo.tools import float_compare, float_is_zero
from odoo.exceptions import ValidationError, UserError, Warning

CANCEL_REASON = [('customer', 'Customer changed/canceled order'),
                 ('inventory', 'Item Unavailable'),
                 ('fraud', 'Fraudulent order'),
                 ('declined', 'Payment declined'),
                 ('other', 'Other')]

DISCREPANCY_REASON = [('restock', 'Restocking Fee'),
                      ('damage', 'Damaged Goods'),
                      ('customer', 'Customer Satisfaction'),
                      ('other', 'Other')]

RESTOCK_TYPE = [('no_restock', 'No Restock'),
                ('cancel', 'Cancel'),
                ('return', 'Return')]


class MKCancelOrder(models.TransientModel):
    _inherit = "mk.cancel.order"

    @api.depends('shopify_refund_payment_lines.price_subtotal', 'shopify_refund_payment_lines.refund_price_unit', 'shopify_shipping_amount')
    def _amount_all(self):
        for record in self:
            shopify_amount_subtotal_to_refund, shopify_tax_amount, order_id = 0.0, 0.0, False
            for line in record.shopify_refund_payment_lines:
                order_id = line.order_line_id.order_id
                taxes = line.order_line_id.tax_id.compute_all(line.price_unit, line.order_line_id.order_id.currency_id, line.to_refund_qty, product=line.product_id,
                                                              partner=line.order_line_id.order_id.partner_shipping_id)
                shopify_tax_amount += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                shopify_amount_subtotal_to_refund += line.refund_price_unit * line.to_refund_qty
            if order_id and self.shopify_shipping_amount > 0.0:
                shipping_line = order_id.order_line.filtered(lambda x: x.is_delivery)
                shipping_taxes = shipping_line.tax_id.compute_all(shipping_line.price_unit, order_id.currency_id, 1, product=shipping_line.product_id,
                                                                  partner=order_id.partner_shipping_id)
                shipping_taxes_total = sum(t.get('amount', 0.0) for t in shipping_taxes.get('taxes', []))
                shopify_tax_amount += shipping_taxes_total
            record.update({
                'shopify_tax_amount': shopify_tax_amount,
                'shopify_amount_subtotal': shopify_amount_subtotal_to_refund,
                'shopify_manual_refund_amount': min(shopify_amount_subtotal_to_refund + shopify_tax_amount + record.shopify_shipping_amount, record.shopify_amount_total),
            })

    shopify_cancel_reason = fields.Selection(CANCEL_REASON, "Cancel Reason", default="customer")
    shopify_is_notify_customer = fields.Boolean("Notify Customer?", default=False, help="Whether to send an email to the customer notifying them of the cancellation.")
    shopify_refund_payment_lines = fields.One2many("shopify.refund.payment.line", "wizard_id", string="Refund payments")
    shopify_amount_total = fields.Monetary(string='Total Available to refund')
    shopify_amount_subtotal = fields.Monetary(string='Subtotal', store=True, readonly=True, compute='_amount_all')
    shopify_remaining_shipping_amount = fields.Monetary(string='Remaining shipping amount to Refund')
    shopify_shipping_amount = fields.Monetary(string='Shipping')
    shopify_tax_amount = fields.Monetary(string="Tax", store=True, compute='_amount_all')
    shopify_manual_refund_amount = fields.Monetary(string='Refund Amount')
    shopify_restock_type = fields.Selection(RESTOCK_TYPE, "Restock Type", default="no_restock", help="How this refund line item affects inventory levels. \n "
                                                                                                     "Valid values : \n"
                                                                                                     "no_restock : Refunding these items won't affect inventory. The number of fulfillable units for this line item will remain unchanged. For example, a refund payment can be issued but no items will be returned or made available for sale again. \n"
                                                                                                     "cancel : The items have not yet been fulfilled. The canceled quantity will be added back to the available count. The number of fulfillable units for this line item will decrease. \n"
                                                                                                     "return : The items were already delivered, and will be returned to the merchant. The returned quantity will be added back to the available count. The number of fulfillable units for this line item will remain unchanged.")

    @api.onchange('shopify_manual_refund_amount')
    def onchange_shopify_manual_refund_amount(self):
        if self.shopify_manual_refund_amount > self.shopify_amount_total:
            self.shopify_manual_refund_amount = self.shopify_amount_total
        return {}

    @api.onchange('shopify_shipping_amount')
    def onchange_shopify_shipping_amount(self):
        if not self.shopify_remaining_shipping_amount and self.shopify_shipping_amount:
            self.shopify_shipping_amount = False
        if self.shopify_shipping_amount > self.shopify_remaining_shipping_amount:
            self.shopify_shipping_amount = self.shopify_remaining_shipping_amount
        return {}

    @api.model
    def default_get(self, fields):
        result = super(MKCancelOrder, self).default_get(fields)
        res_id = self._context.get('active_id')
        order_id = self.env['sale.order'].browse(res_id)
        if not result.get('shopify_refund_payment_lines') and order_id and order_id.marketplace == 'shopify':
            order_id.mk_instance_id.connection_to_shopify()
            try:
                refunds = shopify.Refund.find(order_id=order_id.mk_id)
            except Exception as e:
                raise Warning(e)
            refund_dict_qty_wise = {}
            total_shipping_refunded = 0.0
            total_amount_refunded = 0.0
            for refund in refunds:
                for refund_line in refund.refund_line_items:
                    if refund_dict_qty_wise.get(refund_line.line_item_id, False):
                        refund_dict_qty_wise[refund_line.line_item_id] += refund_line.quantity
                    else:
                        refund_dict_qty_wise.update({refund_line.line_item_id: refund_line.quantity})
                for adjustment in refund.order_adjustments:
                    if adjustment.kind == 'shipping_refund':
                        total_shipping_refunded += float(adjustment.amount)
                for transaction in refund.transactions:
                    if transaction.kind == 'refund':
                        total_amount_refunded += float(transaction.amount)
            shopify_refund_payment_line_ids = self.env['shopify.refund.payment.line']
            remaining_shipping_to_refund = 0.0
            for line in order_id.order_line:
                if line.price_subtotal <= 0:
                    continue
                if line.is_delivery:
                    remaining_shipping_to_refund = line.price_subtotal + total_shipping_refunded
                    continue
                if refund_dict_qty_wise.get(int(line.mk_id), False):
                    available_qty = line.product_uom_qty - refund_dict_qty_wise.get(int(line.mk_id))
                else:
                    available_qty = line.product_uom_qty
                if not available_qty:
                    continue
                shopify_refund_payment_line_ids |= self.env['shopify.refund.payment.line'].create({
                    'product_id': line.product_id.id,
                    'available_qty': available_qty,
                    'to_refund_qty': available_qty,
                    'price_unit': line.price_unit - line.shopify_discount_amount,
                    'refund_price_unit': line.price_unit - line.shopify_discount_amount,
                    'order_line_id': line.id,
                })
            result.update({'shopify_refund_payment_lines': [(6, 0, shopify_refund_payment_line_ids.ids)], 'shopify_remaining_shipping_amount': remaining_shipping_to_refund,
                           'shopify_shipping_amount': remaining_shipping_to_refund, 'shopify_amount_total': order_id.amount_total - total_amount_refunded})
        return result

    def do_cancel_in_shopify(self, order):
        mk_instance_id = order.mk_instance_id
        try:
            mk_instance_id.connection_to_shopify()
            order_id = shopify.Order()
        except Exception as e:
            raise Warning(e)
        order_id.id = order.mk_id
        order_id.reason = self.shopify_cancel_reason
        order_id.email = self.shopify_is_notify_customer
        order_id.cancel()
        order.write({'canceled_in_marketplace': True})
        self._cr.commit()
        return True

    def do_refund_in_shopify(self):
        active_id = self._context.get('active_id')
        order_id = self.env['sale.order'].browse(active_id)
        if not order_id:
            raise Warning(_("Can't find order to cancel. Please go back to order list, open order and try again!"))
        if float_compare((self.shopify_amount_subtotal + self.shopify_shipping_amount + self.shopify_tax_amount), self.shopify_manual_refund_amount, 2) != 0:
            raise Warning(_("Subtotal + Shipping + Tax isn't matching with the Refund Amount. Please adjust refund unit price!"))
        mk_log_id = self.env['mk.log'].create_update_log(mk_instance_id=order_id.mk_instance_id, operation_type='export')
        mk_log_line_dict = self.env.context.get('mk_log_line_dict', {'error': [], 'success': []})
        refund_item_list, restock_type = [], self.shopify_restock_type
        order_id.mk_instance_id.connection_to_shopify()
        for line in self.shopify_refund_payment_lines.filtered(lambda x: x.to_refund_qty):
            refund_item_dict = \
                {'line_item_id': line.order_line_id.mk_id,
                 'quantity': int(line.to_refund_qty),
                 'restock_type': restock_type}
            if restock_type in ['cancel', 'return']:
                shopify_location_id = order_id.shopify_location_id
                if not shopify_location_id:
                    odoo_shopify_location_id = self.env['shopify.location.ts'].search([('is_default_location', '=', True), ('mk_instance_id', '=', order_id.mk_instance_id.id)])
                    shopify_location_id = odoo_shopify_location_id.shopify_location_id
                    if not shopify_location_id:
                        mk_log_line_dict['error'].append(
                            {'log_message': 'Default Shopify Location not found in Odoo while trying to Refund in Shopify. Order: {}'.format(order_id.name)})
                refund_item_dict.update({'location_id': shopify_location_id})
            refund_item_list.append(refund_item_dict)
        if not refund_item_list:
            return False
        shopify_transactions = shopify.Transaction().find(order_id=order_id.mk_id)
        gateway, parent_id = '', ''
        for transaction in shopify_transactions:
            transaction_dict = transaction.to_dict()
            transaction_type = transaction_dict.get('transaction', {}).get('kind') or transaction_dict.get('kind')
            if transaction_type == 'sale':
                parent_id = transaction_dict.get('transaction', {}).get('id') or transaction_dict.get('id')
                gateway = transaction_dict.get('transaction', {}).get('gateway') or transaction_dict.get('gateway')
                break
        vals = {'notify': self.shopify_is_notify_customer,
                'note': self.refund_description or '',
                'order_id': order_id.mk_id,
                'refund_line_items': refund_item_list,
                'transactions': [
                    {
                        'parent_id': parent_id,
                        'amount': self.shopify_manual_refund_amount,
                        'kind': 'refund',
                        'gateway': gateway,
                    }]}
        if self.shopify_shipping_amount:
            vals.update({'shipping': {'amount': self.shopify_shipping_amount}})
        try:
            refund_obj = shopify.Refund()
            response = refund_obj.create(vals)
        except Exception as e:
            raise Warning("Something went wrong while creating a refund in Shopify for order {} : {}".format(order_id.name, e))

        if response.errors and response.errors.errors:
            errors = ",".join(error for error in response.errors.errors.get('base'))
            raise Warning("{}".format(errors))

        shopify_order = shopify.Order.find(order_id.mk_id)
        order_id.write({'shopify_financial_status': shopify_order.financial_status})
        body = _('This order is refunded in Shopify with amount <b>{}</b>'.format(self.shopify_manual_refund_amount))
        order_id.message_post(body=body)
        self.env['mk.log'].create_update_log(mk_instance_id=order_id.mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict=mk_log_line_dict)
        if not mk_log_id.log_line_ids and not self.env.context.get('log_id', False):
            mk_log_id.unlink()
        if self.is_create_refund:
            self.create_shopify_refund_in_odoo(order_id)
        return True

    def cancel_and_refund_in_shopify(self):
        active_id = self._context.get('active_id')
        order_id = self.env['sale.order'].browse(active_id)
        if not order_id:
            raise Warning("Can't find order to cancel. Please go back to order list, open order and try again!")
        self.do_cancel_in_shopify(order_id)
        self.do_refund_in_shopify()
        return True

    def create_shopify_refund_in_odoo(self, order_id):
        invoice_id = order_id.invoice_ids.filtered(lambda x: x.type == 'out_invoice' and x.invoice_payment_state == 'paid')
        if invoice_id:
            move_reversal = self.env['account.move.reversal'].with_context(active_model="account.move", active_ids=invoice_id.ids).create({
                'reason': self.refund_description or "Shopify Refund",
                'refund_method': 'refund',
                'date': self.date_invoice or datetime.now(),
            })
            reversal = move_reversal.reverse_moves()
            refund_invoice = self.env['account.move'].browse(reversal['res_id'])
            to_remove_lines = refund_invoice.invoice_line_ids
            for line in self.shopify_refund_payment_lines.filtered(lambda x: x.to_refund_qty):
                for inv_line in refund_invoice.invoice_line_ids.filtered(lambda x: x.product_id == line.order_line_id.product_id):
                    inv_line.with_context(check_move_validity=False).write({'quantity': line.to_refund_qty, 'price_unit': line.refund_price_unit})
                    to_remove_lines -= inv_line
            if self.shopify_shipping_amount:
                shipping_product_id = order_id.order_line.filtered(lambda x: x.is_delivery).mapped('product_id')
                for inv_line in refund_invoice.invoice_line_ids.filtered(lambda x: x.product_id == shipping_product_id):
                    inv_line.with_context(check_move_validity=False).write({'quantity': 1, 'price_unit': self.shopify_shipping_amount})
                    to_remove_lines -= inv_line
            if to_remove_lines:
                to_remove_lines.with_context(check_move_validity=False).unlink()
            refund_invoice.with_context(check_move_validity=False)._recompute_dynamic_lines(recompute_all_taxes=True, recompute_tax_base_amount=True)
            refund_invoice._check_balanced()
            refund_invoice.action_post()
            register_payments = self.env['account.payment.register'].with_context(active_ids=refund_invoice.ids).create({'journal_id': self.payment_journal_id.id, })
            register_payments.create_payments()
            return reversal
        return True


class ShopifyRefundPaymentLines(models.TransientModel):
    _name = "shopify.refund.payment.line"
    _description = "Shopify Refund Line"

    @api.depends('to_refund_qty')
    def _compute_amount(self):
        for line in self:
            price_subtotal = line.price_unit * line.to_refund_qty
            line.update({'price_subtotal': price_subtotal})

    product_id = fields.Many2one('product.product', string='Product', ondelete='cascade', required=True)
    order_line_id = fields.Many2one('sale.order.line', string="Order Line", ondelete='cascade')
    available_qty = fields.Float(string='Available Quantity', digits='Product Unit of Measure', required=True, default=1.0)
    to_refund_qty = fields.Float(string='To Refund Quantity', digits='Product Unit of Measure', required=True, default=1.0)
    price_unit = fields.Float('Original Unit Price', required=True, digits='Product Price', default=0.0)
    refund_price_unit = fields.Float('Refund Unit Price', required=True, digits='Product Price', default=0.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    wizard_id = fields.Many2one('mk.cancel.order', 'Wizard')
    currency_id = fields.Many2one('res.currency', 'Currency', readonly=True, related='wizard_id.currency_id', store=True)

    @api.onchange('to_refund_qty')
    def onchange_refund_qty(self):
        res = {}
        if not self.available_qty and self.to_refund_qty:
            self.to_refund_qty = False
        if self.to_refund_qty > self.available_qty:
            self.to_refund_qty = self.available_qty
        return res
