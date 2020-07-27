# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from requests.auth import HTTPBasicAuth
import time
import json
import requests
from odoo.exceptions import ValidationError, Warning


class SaleOrder(models.Model):
    _inherit = "sale.order"

    shipstation_order_id = fields.Char('Order ID', help="The system generated identifier for the order.", readonly=True)
    shipstation_account_id = fields.Many2one("shipstation.accounts", "Shipstation Account", ondelete='restrict',
                                             help="Account in which order exist")
    shipstation_store_id = fields.Many2one('shipstation.store', "Store", ondelete='restrict')
    prepared_for_shipstation = fields.Boolean('Prepared for Shipstation')

    # payment_date = fields.Datetime('Payment Date', help="The date the order was paid for.")
    # shipstation_order_status = fields.Selection([('awaiting_payment', 'Awaiting Payment'),
    #                                              ('awaiting_shipment', 'Awaiting Shipment'),
    #                                              ('shipped', 'Shipped'),
    #                                              ('on_hold', 'On Hold'),
    #                                              ('cancelled', 'Cancelled')], string="Order Status")
    # customer_note = fields.Text('Customer Note', help="Notes left by the customer when placing the order.")
    # internal_note = fields.Text('Internal Note', help="Private notes that are only visible to the seller.")
    # is_gift = fields.Boolean('Gift', help="Specifies whether or not this Order is a gift")
    # gift_notes = fields.Text('Gift Note', help="Gift message left by the customer when placing the order.")
    # hold_until_date = fields.Datetime('Hold Until Date',
    #                                   help="If placed on hold, this date is the expiration date for this order's hold status. The order is moved back to awaiting_shipment on this date.")
    # externally_fulfilled = fields.Boolean('Externally Fulfilled',
    #                                       help="States whether the order has is current marked as externally fulfilled by the marketplace. A common example is when an Amazon order is marked an Amazon Fulfilled Network (AFN). If the order is an AFN then this element will be true.",
    #                                       readonly=True)
    # externally_fulfilledBy = fields.Char('Externally FulfilledBy',
    #                                      help="If Externall Fulfilled is true then this string will return how the order is being fulfilled by the marketplace.",
    #                                      readonly=True)
    # TODO : requestedShippingService,

    def import_orders(self, account=False):
        orders = []
        if not account:
            raise Warning("Shipstation Account not defined to import orders")
        request_url = 'orders?pageSize=500&orderStatus=awaiting_shipment'
        if account.order_imported_as_on_date:
            order_date_start = account.order_imported_as_on_date - timedelta(days=3)
            order_date_start = order_date_start.strftime("%Y-%m-%d %H:%M:%S")
            request_url = request_url + '&orderDateStart=%s' % order_date_start
        response = account._send_request(request_url, {}, method='GET')
        if isinstance(response.get('orders'), dict):
            orders = [response.get('orders')]
        orders += response.get('orders')
        total_pages = response.get('pages')
        page = 2
        while total_pages:
            response = account._send_request(request_url + '&page=%s' % page, {}, method='GET')
            order_data = response.get('orders')
            if isinstance(order_data, dict):
                orders += [order_data]
            orders += order_data
            total_pages -= 1
            page += 1
        if orders:
            self.create_shipstation_order(orders, account)
            account.order_imported_as_on_date = datetime.now()
        return orders

    def import_order_from_webhook_notification(self, resource_url, account):
        if not account:
            return True
        account = self.env['shipstation.accounts'].browse(account)
        headers = {
            'Content-Type': 'application/json'
        }
        orders = []
        try:
            req = requests.request('GET', resource_url, auth=HTTPBasicAuth(account.api_key, account.api_secret), headers=headers)
            req.raise_for_status()
            response_text = req.text
        except requests.HTTPError as e:
            response = json.loads(req.text)
            error_msg = ''
            if response.get('ExceptionMessage', False):
                error_msg = response.get('ExceptionMessage', False)
            raise ValidationError(_("Error From ShipStation Webhook: %s" % error_msg or req.text))
        response = json.loads(response_text)
        order_data = response.get('orders')
        if isinstance(order_data, dict):
            orders += [order_data]
        orders += order_data
        if orders:
            self.create_shipstation_order(orders, account)
        return orders

    def check_for_product_exist(self, ss_order_lines, account):
        product_obj = self.env['product.product']
        ss_product_obj = self.env['shipstation.product']
        all_product_exist = True
        for order_line in ss_order_lines:
            product_id = order_line.get('productId', False)
            sku = order_line.get('sku', False)
            name = order_line.get('name', False)
            if not sku:
                all_product_exist = False
                break
            ss_product = ss_product_obj.search(
                ['|', ('shipstation_id', '=', product_id), ('sku', '=', sku), ('account_id', '=', account.id)])
            if ss_product:
                continue
            odoo_product = product_obj.search([('default_code', '=', sku)], limit=1)
            if odoo_product:
                ss_product_obj.create({
                    'name': name,
                    'product_id': odoo_product.id,
                    'shipstation_id': product_id,
                    'sku': sku,
                    'account_id': account.id
                })
            elif account.automatic_product_creation:
                product = product_obj.create({
                    'name': name,
                    'type': 'product',
                    'default_code': sku
                })
                ss_product_obj.create({
                    'name': name,
                    'product_id': product.id,
                    'shipstation_id': product_id,
                    'sku': sku,
                    'account_id': account.id
                })
            else:
                all_product_exist = False
                break
        return all_product_exist

    def prepare_sales_order_vals(self, billing_partner_id, shipping_partner_id, order, account):
        sale_order_obj = self.env['sale.order']
        shipstation_store_obj = self.env['shipstation.store']
        shipstation_warehouse_obj = self.env['shipstation.warehouse']
        shipstation_service_obj = self.env['shipstation.service']
        delivery_carrier_obj = self.env['delivery.carrier']
        advance_option_dict = order.get('advancedOptions', False)
        store_id = shipstation_store_obj.search(
            [('store_id', '=', advance_option_dict.get('storeId')), ('account_id', '=', account.id)])
        warehouse = shipstation_warehouse_obj.search([('shipstation_id', '=', advance_option_dict.get('warehouseId')),
                                                      ('account_id', '=', account.id)]).warehouse_id
        if not warehouse:
            warehouse = account.warehouse_id

        shipstation_service_id = shipstation_service_obj.search(
            [('code', '=', order.get('serviceCode', False))])

        delivery_method = delivery_carrier_obj.search(
            [('delivery_type', '=', 'shipstation_ts'), ('shipstation_account_id', '=', account.id),
             ('shipstation_service_id', '=', shipstation_service_id.id), ('shipstation_store_id', '=', store_id.id)], limit=1)

        ordervals = {
            'company_id': account.company_id.id,
            'partner_id': billing_partner_id,
            'partner_invoice_id': billing_partner_id,
            'partner_shipping_id': shipping_partner_id,
            'warehouse_id': warehouse.id,
        }
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_id()
        ordervals = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_shipping_id()
        ordervals = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})

        order_date = order.get('orderDate', False)[:19]
        order_date = time.strptime(order_date, "%Y-%m-%dT%H:%M:%S")
        order_date = time.strftime("%Y-%m-%d %H:%M:%S", order_date)
        ordervals.update({
            'name': order.get('orderNumber'),
            'shipstation_account_id': account.id or False,
            'picking_policy': account.picking_policy or False,
            'partner_invoice_id': billing_partner_id.id,
            'date_order': order_date,
            'partner_shipping_id': shipping_partner_id.id,
            'pricelist_id': account.pricelist_id.id,
            'shipstation_order_id': order.get('orderId', False),
            'carrier_id': delivery_method and delivery_method.id or False,
            'shipstation_store_id': store_id.id,
        })
        return ordervals

    def prepare_sales_order_line_vals(self, ss_order_lines, account):
        product_obj = self.env['product.product']
        order_val_list = []
        for order_line in ss_order_lines:
            sku = order_line.get('sku', False)
            odoo_product = product_obj.search([('default_code', '=', sku)], limit=1)
            order_line_vals = {
                'order_id': self.id,
                'product_id': odoo_product and odoo_product.id or False,
                'name': order_line.get('name', False),
                'product_uom_qty': order_line.get('quantity', False),
                'price_unit': order_line.get('unitPrice', False),
            }
            new_record = self.env['sale.order.line'].new(order_line_vals)
            new_record.product_id_change()
            order_line_vals = self.env['sale.order.line']._convert_to_write(
                {name: new_record[name] for name in new_record._cache})
            order_line_vals.update({
                'order_id': self.id,
                'product_uom_qty': order_line.get('quantity', False),
                'name': order_line.get('name', False),
                'price_unit': order_line.get('unitPrice', False),
                'discount': 0.0,
                'product_uom': new_record.product_uom.id
            })
            order_val_list.append(order_line_vals)
        return order_val_list

    def create_shipstation_order(self, orders, account):
        res_partner_obj = self.env['res.partner']
        sale_line_obj = self.env['sale.order.line']
        for order in orders:
            ss_order_id = order.get('orderId', False)
            ss_order_lines = order.get('items')
            if not ss_order_id or not ss_order_lines:
                continue
            existing_order = self.search([('shipstation_order_id', '=', ss_order_id)])
            if existing_order:
                # TODO: Updates important value in existing sale order
                continue
            all_product_exist = self.check_for_product_exist(ss_order_lines, account)
            if not all_product_exist:
                continue
            billing_address_info = order.get('billTo')
            shipping_address_info = order.get('shipTo')
            billing_partner_id = res_partner_obj.ss_find_existing_or_create_partner(billing_address_info,
                                                                                    company=account.company_id,
                                                                                    type='invoice')
            shipping_address_info.update({'parent_id': billing_partner_id.id})
            shipping_partner_id = res_partner_obj.ss_find_existing_or_create_partner(shipping_address_info,
                                                                                     company=account.company_id,
                                                                                     type='delivery')

            order_vals = self.prepare_sales_order_vals(billing_partner_id, shipping_partner_id, order, account)
            order_id = self.create(order_vals)
            order_line_vals = order_id.prepare_sales_order_line_vals(ss_order_lines, account)
            for line in order_line_vals:
                sale_line_obj.create(line)
            if order.get('shippingAmount') and account.shipping_product_id:
                order_line = {
                    'order_id': order_id.id,
                    'product_id': account.shipping_product_id.id,
                }
                new_order_line = sale_line_obj.new(order_line)
                new_order_line.product_id_change()
                order_line = sale_line_obj._convert_to_write(
                    {name: new_order_line[name] for name in new_order_line._cache})
                order_line.update({
                    'sequence': 100,
                    'price_unit': order.get('shippingAmount'),
                    'is_delivery': True
                })
                sale_line_obj.create(order_line)
            order_id.action_confirm()
        return True
