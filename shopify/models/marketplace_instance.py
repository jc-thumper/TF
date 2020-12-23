import json
import requests
from .. import shopify
from urllib.parse import urlparse
from odoo import models, fields, api, _
from odoo.modules.module import get_module_resource
from odoo.exceptions import ValidationError, AccessError

ACCOUNT_STATE = [('not_confirmed', 'Not Confirmed'), ('confirmed', 'Confirmed')]


class MkInstance(models.Model):
    _inherit = "mk.instance"

    def _get_mk_kanban_counts(self):
        super(MkInstance, self)._get_mk_kanban_counts()
        for mk_instance_id in self:
            mk_instance_id.shopify_collection_count = len(mk_instance_id.shopify_collection_ids)
            mk_instance_id.shopify_location_count = len(mk_instance_id.shopify_location_ids)

    def _get_default_fulfillment_status(self):
        fulfillment_status_id = self.env.ref('shopify.shopify_order_status_unshipped', raise_if_not_found=False)
        return [(6, 0, [fulfillment_status_id.id])] if fulfillment_status_id else False

    def _get_shopify_discount_product(self):
        return self.env.ref('shopify.shopify_discount', raise_if_not_found=False) or False

    def _get_shopify_delivery_product(self):
        return self.env.ref('shopify.shopify_delivery', raise_if_not_found=False) or False

    def _get_shopify_custom_product(self):
        return self.env.ref('shopify.shopify_custom_line_product', raise_if_not_found=False) or False

    def shopify_mk_default_api_limit(self):
        return 250

    marketplace = fields.Selection(selection_add=[('shopify', _("Shopify"))], required=True, string='Marketplace')
    api_key = fields.Char("API Key", copy=False)
    password = fields.Char("Password", copy=False)
    shared_secret = fields.Char("Shared Secret", copy=False)
    shop_url = fields.Char("Shop URL", copy=False, help="Exp. https://teqstars.myshopify.com")

    # Sale Orders Fields
    close_order_after_fulfillment = fields.Boolean("Close Order after Fulfillment?", help="If true then at the time of Update Order Status closing Shopify Order.")

    fulfillment_status_ids = fields.Many2many('shopify.order.status', 'marketplace_order_status_rel', 'mk_instance_id', 'status_id', "Fulfillment Status",
                                              default=_get_default_fulfillment_status, help="Filter orders by their fulfillment status at the time of Import Orders.")
    financial_workflow_config_ids = fields.One2many("shopify.financial.workflow.config", "mk_instance_id", "Financial Workflow Configuration")
    custom_product_id = fields.Many2one('product.product', string='Custom Product', domain=[('type', '=', 'consu')], default=_get_shopify_custom_product,
                                        help="Shopify order with having custom item will be imported with this product in order (Only consumable).")

    # Email & Notification
    is_notify_customer = fields.Boolean("Nofity Customer?", default=False,
                                        help="Whether the customer should be notified. If set to true, then an email will be sent when the fulfillment is created or updated.")

    # Webhook
    webhook_url = fields.Char("Webhook URL", copy=False)
    webhook_ids = fields.One2many("shopify.webhook.ts", "mk_instance_id", "Webhooks")

    # Dashboard fields
    shopify_collection_ids = fields.One2many('shopify.collection.ts', 'mk_instance_id', string="Collections")
    shopify_collection_count = fields.Integer("Collection Count", compute='_get_mk_kanban_counts')
    shopify_location_ids = fields.One2many('shopify.location.ts', 'mk_instance_id', string="Locations")
    shopify_location_count = fields.Integer("Location Count", compute='_get_mk_kanban_counts')

    # Payout Fields
    # payout_report_last_sync_date = fields.Date("Payout Last Sync Date")
    # payout_journal_id = fields.Many2one('account.journal', string='Payout Journal', domain="[('company_id', '=', company_id)]")

    @api.model
    def create(self, vals):
        if vals.get('marketplace', '') == 'shopify':
            if not urlparse(vals.get('shop_url', '')).scheme:
                raise ValidationError(_("URL must include http or https!"))
            if vals.get('shop_url', '').endswith('/'):
                vals.update({'shop_url': vals.get('shop_url')[:-1]})
        res = super(MkInstance, self).create(vals)
        if vals.get('marketplace', '') == 'shopify':
            # Create Webhook URL
            odoo_url = self.env['ir.config_parameter'].get_param('web.base.url')
            instance_url = "{}/{}".format(self.env.cr.dbname, res.id)
            res.webhook_url = odoo_url + '/shopify/webhook/notification/' + instance_url
            # res.fetch_shopify_webhook() TODO: Remove comment while launch app.
        return res

    def write(self, vals):
        if vals.get('marketplace') == 'shopify' or self.marketplace == 'shopify':
            # Create Webhook URL
            odoo_url = self.get_base_url()
            instance_url = "{}/{}".format(self.env.cr.dbname, self.id)
            vals.update({'webhook_url': odoo_url + '/shopify/webhook/notification/' + instance_url})
        if vals.get('api_limit', False) and vals.get('api_limit') > 250 and self.marketplace == 'shopify':
            raise ValidationError(_("You cannot set API Fetch record limit more than 250."))
        if 'shop_url' in vals and vals.get('shop_url', '').endswith('/'):
            vals.update({'shop_url': vals.get('shop_url')[:-1]})
        res = super(MkInstance, self).write(vals)
        for rec in self:
            if rec.marketplace == 'shopify' and not urlparse(rec.shop_url).scheme:
                raise ValidationError(_("URL must include http or https protocol!"))
        return res

    def shopify_mk_kanban_badge_color(self):
        return "#95BF46"

    def shopify_mk_kanban_image(self):
        return get_module_resource('shopify', 'static/description', 'shopify_logo.png')

    def connection_to_shopify(self):
        parsed_url = urlparse(self.shop_url)
        shop_url = "{scheme}://{api_key}:{password}@{shop_url}/admin/api/2019-10".format(api_key=self.api_key, password=self.password, scheme=parsed_url.scheme,
                                                                                         shop_url=parsed_url.netloc)
        shopify.ShopifyResource.set_site(shop_url)
        return True

    def shopify_action_confirm(self):
        self.connection_to_shopify()
        try:
            shop = shopify.Shop.current()
            shop_dict = shop.to_dict()
            self.set_pricelist(shop_dict.get('currency'))
        except Exception as e:
            raise AccessError(e)
        self.env['shopify.location.ts'].import_location_from_shopify(self)

    def reset_to_draft(self):
        res = super(MkInstance, self).reset_to_draft()

        if self.marketplace == 'shopify':
            self.connection_to_shopify()
            for webhook in self.webhook_ids:
                webhook.shopify_delete_webhook()
        return res

    def fetch_shopify_webhook(self):
        self.env['shopify.webhook.ts'].fetch_all_webhook_from_shopify(self)
        return True

    def shopify_api_call(self, method='GET', url='', data=None, params=False, full_url=False):
        if data is None:
            data = {}
        try:
            shop_url = self.shop_url + url if self.shop_url.endswith('/') else self.shop_url + '/' + url
            if full_url:
                shop_url = full_url
            if data:
                data = json.dumps(data)
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
            response = requests.request(method, shop_url, auth=(self.api_key, self.password), headers=headers, data=data, params=params)
        except Exception as e:
            return e
        return response

    def shopify_setup_schedule_actions(self, mk_instance_id):
        cron_obj = self.env['ir.cron']
        cron_name = 'Marketplace[{}] : Auto Import Shopify Sale Order'.format(mk_instance_id.name)
        cron_obj.create_marketplace_cron(mk_instance_id, cron_name, method_name='cron_auto_import_shopify_orders', model_name='sale.order', interval_type='minutes',
                                         interval_number=15)
        cron_name = 'Marketplace[{}] : Auto Update Shopify Sale Order'.format(mk_instance_id.name)
        cron_obj.create_marketplace_cron(mk_instance_id, cron_name, method_name='cron_auto_update_order_status', model_name='sale.order', interval_type='minutes',
                                         interval_number=25)
        cron_name = 'Marketplace[{}] : Auto Export Shopify Product\'s Stock'.format(mk_instance_id.name)
        cron_obj.create_marketplace_cron(mk_instance_id, cron_name, method_name='cron_auto_export_stock', model_name='mk.listing', interval_type='minutes', interval_number=30)
        cron_name = 'Marketplace[{}] : Auto Import Shopify Product\'s Stock'.format(mk_instance_id.name)
        cron_obj.create_marketplace_cron(mk_instance_id, cron_name, method_name='cron_auto_import_stock', model_name='mk.listing', interval_type='days', interval_number=1)
        # cron_name = 'Marketplace[{}] : Import Payout Reports'.format(mk_instance_id.name)
        # cron_obj.create_marketplace_cron(mk_instance_id, cron_name, method_name='shopify_import_payout_report', model_name='shopify.payout', interval_type='days',
        #                                  interval_number=1)
        # cron_name = 'Marketplace[{}] : Process Payout Reports'.format(mk_instance_id.name)
        # cron_obj.create_marketplace_cron(mk_instance_id, cron_name, method_name='shopify_process_payout_report', model_name='shopify.payout', interval_type='days',
        #                                  interval_number=1)
        return True
