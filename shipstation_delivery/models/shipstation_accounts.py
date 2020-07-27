# -*- coding: utf-8 -*-
import json
import pytz
import requests
from datetime import datetime
from email.utils import formataddr
from requests.auth import HTTPBasicAuth
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, Warning

SHIPSTATION_ENDPOINT = 'https://ssapi.shipstation.com/'


class ShipstationAccounts(models.Model):
    _name = "shipstation.accounts"

    name = fields.Char("Name", required=True, copy=False, help="Name of your shipstation account")

    # Authentication
    api_key = fields.Char('API Key', required=True, copy=False)
    api_secret = fields.Char('API Secret', required=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    picking_policy = fields.Selection([
        ('direct', 'Deliver each product when available'),
        ('one', 'Deliver all products at once')],
        string='Shipping Policy', default='direct')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist',
                                   help="Pricelist for to be import sales order.")
    shipping_product_id = fields.Many2one('product.product', string="Shipping Product",
                                          help="It will be set as new line when order has shipping charge.")
    automatic_product_creation = fields.Boolean('Create Product if not found?', default=True)
    # order_status_ids = fields.One2many('order.workflow', 'account_id', string="Order Status Mapping")

    order_imported_as_on_date = fields.Datetime('Last Order Import Date', copy=False)
    carrier_balance = fields.Float('Lowest Carrier Balance', help="Notify if related carrier balance not enough.")
    notify_partners_ids = fields.Many2many('res.partner', string='Notify to Users',
                                           help="If balance was not enough on the this account carriers so send email to selected users.")
    auto_import_orders = fields.Boolean("Auto Import Orders?", copy=False, default=True)

    # from_date = fields.Date('From Date')
    # carr_id=fields.Many2one('shipstatn.carrier','Carrier Name')
    # allow_multiple_label=fields.Boolean("Allow Label Creation Multiple Times")
    # export_order_create = fields.Boolean("Export Order at Creation")

    _sql_constraints = [
        ('api_keys_uniq', 'unique(api_key, api_secret)', 'API keys must be unique per Shipstation Account!'),
    ]

    @api.model
    def action_dashboard_redirect(self):
        return self.env.ref('shipstation_delivery.dashboard').read()[0]

    @api.model
    def _send_request(self, request_url, request_data, method='GET'):
        headers = {
            'Content-Type': 'application/json'
        }
        data = json.dumps(request_data)
        api_url = SHIPSTATION_ENDPOINT + request_url
        try:
            req = requests.request(method, api_url, auth=HTTPBasicAuth(self.api_key, self.api_secret), headers=headers,
                                   data=data)
            req.raise_for_status()
            response_text = req.text
        except requests.HTTPError as e:
            response = json.loads(req.text)
            error_msg = ''
            if response.get('ExceptionMessage', False):
                error_msg = response.get('ExceptionMessage', False)
            raise ValidationError(_("Error From ShipStation : %s" % error_msg or req.text))
        response = json.loads(response_text)
        return response

    def covert_date(self, value):
        ts = "%s %s" % (value.partition(
            'T')[0], value.partition('T')[2].partition('.')[0])
        value = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
        # tz_name = self.env.context.get('tz') or self.env.user.tz
        # if tz_name:
        #     user_tz = pytz.timezone(tz_name)
        #     utc = pytz.utc
        #
        #     value = user_tz.localize(value).astimezone(utc)
        return value

    def get_order_import_cron(self):
        action = self.env.ref('base.ir_cron_act').read()[0]
        auto_import_cron = self.env.ref('shipstation_delivery.auto_order_import_shipstation')
        if auto_import_cron:
            action['views'] = [(False, 'form')]
            action['res_id'] = auto_import_cron.id
        else:
            raise ValidationError(_("Scheduled action isn't found! Please upgrade app to get it back!"))
        return action

    def import_marketplaces(self):
        shipstation_marketplace = self.env['shipstation.marketplace']
        for account in self:
            shipstation_marketplace.import_marketplaces(account)
        return True

    def import_stores(self):
        shipstation_store = self.env['shipstation.store']
        for account in self:
            shipstation_store.import_stores(account)
        return True

    def import_carrier(self):
        shipstation_carrier = self.env['shipstation.carrier']
        for account in self:
            shipstation_carrier.import_carrier(account)
        return True

    def carrier_services(self):
        shipstation_service = self.env['shipstation.service']
        for account in self:
            shipstation_service.import_services(account)
        return True

    def import_customer(self):
        res_partner = self.env['res.partner']
        for account in self:
            res_partner.import_customer(account)
        return True

    def import_orders(self):
        sale_order = self.env['sale.order']
        for account in self:
            sale_order.import_orders(account)
        return True

    def import_products(self):
        shipstation_product = self.env['shipstation.product']
        for account in self:
            shipstation_product.import_products(account)
        return True

    def import_warehouse(self):
        shipstation_warehouse = self.env['shipstation.warehouse']
        for account in self:
            shipstation_warehouse.import_warehouse(account)
        return True

    def test_connection(self):
        response = self._send_request('stores/marketplaces', {})
        if response:
            raise Warning("Test Connection Succeeded")
        return True

    @api.model
    def auto_import_orders_cron(self):
        for account in self.search([('auto_import_orders', '=', True)]):
            account.import_orders()
        return True

    @api.model
    def notify_carrier_balance_shipstation(self):
        total_accounts = self.search([])
        for account in total_accounts:
            ctx = self._context.copy()
            carrier_data = []
            user_emails = account.notify_partners_ids.mapped('email')
            carriers = self.env['shipstation.carrier'].search([('account_id', '=', account.id)])
            for carrier in carriers:
                if account.carrier_balance >= carrier.balance:
                    carrier_data.append({'account': account.name, 'carrier': carrier.name, 'balance': carrier.balance})
            if carrier_data and any(user_emails):
                email_to = ','.join(formataddr(('', email)) for email in user_emails)
                ctx.update({'email_to': email_to, 'carrier_data': carrier_data})
                template = self.env.ref('shipstation_delivery.email_template_data_notify_carrier_balance_1', False)
                template.with_context(ctx).send_mail(account.id, force_send=True)
        return True

# class OrderStatusMapping(models.Model):
#     _name = "order.workflow"
#     _description = "Order Workflow"
#
#     shipstation_status = fields.Selection([('awaiting_payment', 'Awaiting Payment'),
#                                            ('awaiting_shipment', 'Awaiting Shipment'),
#                                            ('shipped', 'Shipped'),
#                                            ('on_hold', 'On Hold'),
#                                            ('cancelled', 'Cancelled')], string="Shipstation Status", required=True)
#     odoo_status = fields.Selection([('draft', 'Quotation'),
#                                     ('sale', 'Sales Order'),
#                                     ('shipped', 'Shipped'),
#                                     ('done', 'Locked'),
#                                     ('cancel', 'Cancelled'),
#                                     ], string='Odoo Status', required=True)
#
#     create_invoice = fields.Boolean('Create Invoice')
#     validate_invoice = fields.Boolean('Validate Invoice')
#     apply_payment = fields.Boolean('Apply Payment')
#     payment_journal_id = fields.Many2one('account.journal', string="Payment Journal",
#                                          domain=[('type', 'in', ['cash', 'bank'])])
#     account_id = fields.Many2one('shipstation.accounts', string="Account", required=True)
#
#     @api.onchange("odoo_status")
#     def onchange_odoo_status(self):
#         for record in self:
#             if record.odoo_status in ['draft', 'cancel']:
#                 record.create_invoice = False
#
#     @api.onchange("create_invoice")
#     def onchange_create_invoice(self):
#         for record in self:
#             if not record.create_invoice:
#                 record.validate_invoice = False
#
#     @api.onchange("validate_invoice")
#     def onchange_validate_invoice(self):
#         for record in self:
#             if not record.validate_invoice:
#                 record.apply_payment = False
#
#     @api.onchange("apply_payment")
#     def onchange_apply_payment(self):
#         for record in self:
#             if not record.apply_payment:
#                 record.payment_journal_id = False
