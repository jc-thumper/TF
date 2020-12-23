import sys
import odoo
from .. import shopify
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger("Teqstars:Shopify")

WEBHOOK_EVENTS = [('customers/create', 'Create Customer'),
                  ('customers/update', 'Update Customer'),
                  ('orders/create', 'Create Orders'),
                  ('products/create', 'Create Product'),
                  ('products/update', 'Update Product'),
                  ('products/remove', 'Delete Product'),
                  ('collections/create', 'Create Collections'),
                  ('collections/update', 'Update Collections'),
                  ('collections/delete', 'Delete Collections')]


class ShopifyWebhook(models.Model):
    _name = "shopify.webhook.ts"
    _description = "Shopify Webhook"

    name = fields.Char("Name", required=1)
    webhook_event = fields.Selection(WEBHOOK_EVENTS, "Webhook Event Type")
    webhook_id = fields.Char("Webhook ID", copy=False)
    active_webhook = fields.Boolean("Active", default=False)
    mk_instance_id = fields.Many2one('mk.instance', "Instance", ondelete='cascade')

    _sql_constraints = [('event_account_unique', 'unique(webhook_event,mk_instance_id)', 'You cannot create duplicate Webhook Events.')]

    def fetch_all_webhook_from_shopify(self, mk_instance_id):
        mk_instance_id.connection_to_shopify()
        webhooks = shopify.Webhook().find()
        for webhook in webhooks:
            webhook_dict = webhook.to_dict()
            webhook_id = webhook_dict.get('id')
            webhook_event = webhook_dict.get('topic')
            if webhook_dict.get('address') != mk_instance_id.webhook_url:
                continue
            existing_webhook_id = self.search([('mk_instance_id', '=', mk_instance_id.id), ('webhook_id', '=', webhook_id)])
            if not existing_webhook_id:
                create_vals = {'name': dict(self._fields['webhook_event'].selection).get(webhook_event),
                               'webhook_event': webhook_event,
                               'webhook_id': webhook_id,
                               'active_webhook': True,
                               'mk_instance_id': mk_instance_id.id}
                self.with_context(skip_create=True).create(create_vals)
        return True

    def create_webhook_in_shopify(self, vals, mk_instance_id):
        mk_instance_id.connection_to_shopify()
        if not mk_instance_id.webhook_url.startswith('https://'):
            raise ValidationError("You can only create Webhook with secure URL (https).")
        data_vals = {"webhook": {"topic": self.webhook_event, "address": mk_instance_id.webhook_url, "format": "json"}}
        request_url = 'admin/api/2020-01/webhooks.json'
        response = mk_instance_id.shopify_api_call('POST', request_url, data_vals)
        if response.status_code not in [200, 201]:
            raise AccessError(response.text)
        response_dict = response.json()
        webhook_id = response_dict.get('webhook', {}).get('id')
        vals.update({'webhook_id': webhook_id})
        return vals

    @api.model
    def create(self, vals):
        res = super(ShopifyWebhook, self).create(vals)
        if vals.get('active_webhook') and not self.env.context.get('skip_create', False):
            mk_instance_id = self.env['mk.instance'].browse(vals.get('mk_instance_id'))
            res.create_webhook_in_shopify(vals, mk_instance_id)
        return res

    def write(self, vals):
        if vals.get('active_webhook'):
            self.create_webhook_in_shopify(vals, self.mk_instance_id)
        if 'active_webhook' in vals and not vals.get('active_webhook', False) and self.webhook_id:
            try:
                self.mk_instance_id.connection_to_shopify()
                shopify_webhook = shopify.Webhook().find(self.webhook_id)
                shopify_webhook.destroy()
            except Exception as err:
                _logger.error("SHOPIFY WEBHOOK WRITE: Cannot found webhook in Shopify. ERROR: {}".format(err))
        res = super(ShopifyWebhook, self).write(vals)
        return res

    def unlink(self):
        for record in self:
            if record.active_webhook:
                record.mk_instance_id.connection_to_shopify()
                try:
                    shopify_webhook = shopify.Webhook().find(record.webhook_id)
                    shopify_webhook.destroy()
                except Exception as err:
                    _logger.error("SHOPIFY WEBHOOK UNLINK: Cannot found webhook in Shopify. ERROR: {}".format(err))
        res = super(ShopifyWebhook, self).unlink()
        return res

    def shopify_delete_webhook(self):
        self.active_webhook = False
        return True
