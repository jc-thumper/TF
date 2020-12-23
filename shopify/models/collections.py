import base64
import requests
from .. import shopify
import urllib.parse as urlparse
from odoo import models, fields, _
from .misc import convert_shopify_datetime_to_utc
from odoo.exceptions import AccessError, ValidationError
import logging
_logger = logging.getLogger("Teqstars:Shopify")

SORT_ORDER_SELECTION = [('alpha-asc', 'Alphabetically, in ascending order (A - Z)'),
                        ('alpha-desc', 'Alphabetically, in descending order (Z - A)'),
                        ('best-selling', 'By best-selling products'),
                        ('created', 'By date created, in ascending order (oldest - newest)'),
                        ('created-desc', 'By date created, in descending order (newest - oldest)'),
                        ('manual', 'Order created by the shop owner'),
                        ('price-asc', 'By price, in ascending order (lowest - highest)'),
                        ('price-desc', 'By price, in descending order (highest - lowest)')]
PUBLISHED_SCOPE_SELECTION = [('web', 'Publish to the Online Store channel.'),
                             ('global', 'Publish to Online Store channel and the Point of Sale channel.')]
COLLECTION_TYPE = [('automated', 'Automated'), ('manual', 'Manual')]


class ShopifyCollection(models.Model):
    _name = "shopify.collection.ts"
    _description = "Collection"

    def _product_count(self):
        for collection_id in self:
            collection_id.product_count = len(collection_id.mk_listing_ids)

    name = fields.Char("Name", size=255, required=1)
    mk_instance_id = fields.Many2one('mk.instance', "Instance", ondelete='cascade')
    shopify_collection_id = fields.Char("Collection ID")
    collection_type = fields.Selection(COLLECTION_TYPE, "Collection Type")
    exported_in_shopify = fields.Boolean("Exported in Shopify")
    image = fields.Binary("Image", help="Image associated with the custom collection.")
    handle = fields.Char("Handle", size=255,
                         help="A human-friendly unique string for the custom collection automatically generated from its title. This is used in shop themes by the Liquid templating language to refer to the custom collection.")
    shopify_update_date = fields.Datetime("Update Date",
                                          help="The date and time when the custom collection was last modified.")
    shopify_publish_date = fields.Datetime("Publish Date",
                                           help="The time and date when the collection was made visible.")
    sort_order = fields.Selection(SORT_ORDER_SELECTION, "Sort Order", default="manual")
    template_suffix = fields.Char("Template Suffix",
                                  help="The suffix of the liquid template being used. For example, if the value is custom, then the collection is using the "
                                       "collection.custom.liquid template. If the value is null, then the collection is using the default collection.liquid.")
    description = fields.Html('Description', sanitize_attributes=False,
                              help="The description of the custom collection, complete with HTML markup. Many templates display this on their custom collection pages.")
    published_scope = fields.Selection(PUBLISHED_SCOPE_SELECTION, "Published Scope", default="web")
    mk_listing_ids = fields.Many2many("mk.listing", "shopify_collection_tmpl_rel", "collection_id", "template_id", "Shopify Product Templates")
    product_count = fields.Integer("Variants", compute='_product_count')
    is_disjunctive = fields.Boolean("Disjunctive", default=False,
                                    help="Whether the product must match all the rules to be included in the smart collection.\n"
                                         "True: Products only need to match one or more of the rules to be included in the smart collection.\n"
                                         "False: Products must match all of the rules to be included in the smart collection.")
    collection_condition_ids = fields.One2many("shopify.collection.condition.ts", "shopify_collection_id",
                                               string="Conditions")
    is_available_in_website = fields.Boolean("Available in Website")

    def publish_collection_in_shopify(self):
        mk_instance_id = self.mk_instance_id
        mk_instance_id.connection_to_shopify()
        if self.shopify_collection_id:
            try:
                if self.collection_type == 'automated':
                    shopify_collection = shopify.SmartCollection.find(self.shopify_collection_id)
                else:
                    shopify_collection = shopify.CustomCollection.find(self.shopify_collection_id)
                shopify_collection.published = 'true'
                shopify_collection.id = self.shopify_collection_id
                published_at = fields.Datetime.now()
                published_at = published_at.strftime("%Y-%m-%dT%H:%M:%S")
                shopify_collection.published_at = published_at
                result = shopify_collection.save()
                if result:
                    result_dict = shopify_collection.to_dict()
                    self.write({'shopify_update_date': convert_shopify_datetime_to_utc(result_dict.get('updated_at')),
                                'shopify_publish_date': convert_shopify_datetime_to_utc(result_dict.get('published_at')),
                                'is_available_in_website': True})
            except Exception as e:
                raise AccessError(_(e))
        return True

    def unpublish_collection_in_shopify(self):
        mk_instance_id = self.mk_instance_id
        mk_instance_id.connection_to_shopify()
        if self.shopify_collection_id:
            try:
                if self.collection_type == 'automated':
                    shopify_collection = shopify.SmartCollection.find(self.shopify_collection_id)
                else:
                    shopify_collection = shopify.CustomCollection.find(self.shopify_collection_id)
                shopify_collection.published = 'false'
                shopify_collection.published_at = None
                shopify_collection.id = self.shopify_collection_id
                result = shopify_collection.save()
                if result:
                    result_dict = shopify_collection.to_dict()
                    updated_at = result_dict.get('updated_at')
                    self.write({'shopify_update_date': updated_at,
                                'shopify_publish_date': False,
                                'is_available_in_website': False})
            except Exception as e:
                raise AccessError(_(e))
        return True

    def shopify_published(self):
        if not self.is_available_in_website:
            self.publish_collection_in_shopify()
        else:
            self.unpublish_collection_in_shopify()
        return True

    def action_collection_products(self):
        form_id = self.env.ref('base_marketplace.mk_listing_form_view')
        list_id = self.env.ref('base_marketplace.mk_listing_tree_view')
        action = {
            'name': _('Collection Products'),
            'view_id': False,
            'res_model': 'mk.listing',
            'domain': [('id', 'in', self.mk_listing_ids.ids)],
            'context': self._context,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'views': [(list_id.id, 'tree'), (form_id.id, 'form')],
            'type': 'ir.actions.act_window',
        }
        return action

    def fetch_all_shopify_manual_collections(self, limit=250):
        try:
            page_info, shopify_manual_collection_list = False, []
            while 1:
                if page_info:
                    page_wise_manual_collection_list = shopify.CustomCollection().find(limit=limit, page_info=page_info)
                else:
                    page_wise_manual_collection_list = shopify.CustomCollection().find(limit=limit)

                page_url = page_wise_manual_collection_list.next_page_url
                parsed = urlparse.parse_qs(page_url)
                page_info = parsed.get('page_info', False) and parsed.get('page_info', False)[0] or False
                shopify_manual_collection_list = page_wise_manual_collection_list + shopify_manual_collection_list

                if not page_info:
                    break
            return shopify_manual_collection_list
        except Exception as e:
            raise AccessError(e)

    def fetch_all_shopify_automated_collections(self, limit=250):
        try:
            page_info, shopify_automated_collection_list = False, []
            while 1:
                if page_info:
                    page_wise_automated_collection_list = shopify.SmartCollection().find(limit=limit, page_info=page_info)
                else:
                    page_wise_automated_collection_list = shopify.SmartCollection().find(limit=limit)
                page_url = page_wise_automated_collection_list.next_page_url
                parsed = urlparse.parse_qs(page_url)
                page_info = parsed.get('page_info', False) and parsed.get('page_info', False)[0] or False
                shopify_automated_collection_list = page_wise_automated_collection_list + shopify_automated_collection_list
                if not page_info:
                    break
            return shopify_automated_collection_list
        except Exception as e:
            raise AccessError(e)

    def sync_collection_products(self, collection, mk_instance_id=None):
        mk_listing_obj = self.env['mk.listing']
        mk_instance_id = self.mk_instance_id or mk_instance_id
        shopify_product_list = []
        for product in collection.products():
            shopify_product_template_id = mk_listing_obj.search([('mk_id', '=', product.id), ('mk_instance_id', '=', mk_instance_id.id)])
            if not shopify_product_template_id:
                mk_listing_obj.shopify_import_listings(mk_instance_id, mk_listing_id=str(product.id))
                shopify_product_template_id = mk_listing_obj.search([('mk_id', '=', product.id), ('mk_instance_id', '=', mk_instance_id.id)])
            if not shopify_product_template_id:
                log_message = "Odoo Product {} not found for a Collection {}".format(product.id, collection.id)
                _logger.error(log_message)
            else:
                shopify_product_list.append(product.id)
        return shopify_product_list

    def create_update_collections(self, collection_dict, collection_type, mk_instance_id):
        published_scope = collection_dict.get('published_scope', '')
        condition_list = collection_dict.get('rules')
        shopify_collection_id = collection_dict.get('id', '')
        shopify_update_date = convert_shopify_datetime_to_utc(collection_dict.get('published_at', ''))
        vals = {'shopify_collection_id': shopify_collection_id,
                'name': collection_dict.get('title', ''),
                'handle': collection_dict.get('handle', ''),
                'shopify_update_date': convert_shopify_datetime_to_utc(collection_dict.get('updated_at', '')),
                'shopify_publish_date': shopify_update_date,
                'sort_order': collection_dict.get('sort_order', ''),
                'template_suffix': collection_dict.get('template_suffix', ''),
                'description': collection_dict.get('body_html', ''),
                'published_scope': published_scope,
                'is_available_in_website': True if shopify_update_date else False,
                'exported_in_shopify': True,
                'mk_instance_id': mk_instance_id.id,
                'collection_type': collection_type}
        if collection_dict.get("image", False):
            url = collection_dict.get("image", {}).get('src', '')
            if url:
                url = url.replace('\\', '')
                vals.update({'image': base64.b64encode(requests.get(url).content)})

        odoo_shopify_collection_id = self.search([('shopify_collection_id', '=', shopify_collection_id), ('mk_instance_id', '=', mk_instance_id.id)], limit=1)
        if odoo_shopify_collection_id:
            odoo_shopify_collection_id.write(vals)
        else:
            odoo_shopify_collection_id = self.create(vals)
        if condition_list:
            condition_vals = []
            for condition_dict in condition_list:
                odoo_shopify_collection_id.write({'collection_condition_ids': [(2, line_id.id, False) for line_id in
                                                                               odoo_shopify_collection_id.collection_condition_ids]})
                condition_vals.append((0, 0, {'shopify_collection_id': odoo_shopify_collection_id.id,
                                              'column': condition_dict.get('column'),
                                              'relation': condition_dict.get('relation'),
                                              'condition': condition_dict.get('condition')}))
            odoo_shopify_collection_id.write({'collection_condition_ids': condition_vals})
        return odoo_shopify_collection_id

    def import_shopify_collections(self, mk_instance_id):
        mk_listing_obj = self.env['mk.listing']
        mk_instance_id.connection_to_shopify()
        shopify_manual_collection_list = self.fetch_all_shopify_manual_collections(mk_instance_id.api_limit)
        for shopify_manual_collection in shopify_manual_collection_list:
            shopify_manual_collection_dict = shopify_manual_collection.to_dict()
            manual_collection_id = self.create_update_collections(shopify_manual_collection_dict, 'manual', mk_instance_id)
            shopify_product_list = self.sync_collection_products(shopify_manual_collection, mk_instance_id=mk_instance_id)
            mk_listing_ids = mk_listing_obj.search([('mk_id', 'in', shopify_product_list), ('mk_instance_id', '=', mk_instance_id.id)])
            manual_collection_id.write({'mk_listing_ids': [(6, 0, mk_listing_ids.ids)]})
            self._cr.commit()

        shopify_automated_collection_list = self.fetch_all_shopify_automated_collections(mk_instance_id.api_limit)
        for shopify_automated_collection in shopify_automated_collection_list:
            shopify_automated_collection_dict = shopify_automated_collection.to_dict()
            automated_collection_id = self.create_update_collections(shopify_automated_collection_dict, 'automated', mk_instance_id)
            shopify_product_list = self.sync_collection_products(shopify_automated_collection, mk_instance_id=mk_instance_id)
            mk_listing_ids = mk_listing_obj.search([('mk_id', 'in', shopify_product_list), ('mk_instance_id', '=', mk_instance_id.id)])
            automated_collection_id.write({'mk_listing_ids': [(6, 0, mk_listing_ids.ids)]})
            self._cr.commit()
        return True

    def prepare_collection_vals(self):
        collection_vals = {'title': self.name}
        if self.description:
            collection_vals.update({'body_html': self.description})
        if self.template_suffix:
            collection_vals.update({'template_suffix': self.template_suffix})
        if self.sort_order:
            collection_vals.update({'sort_order': self.sort_order})
        if self.is_available_in_website:
            collection_vals.update({'published': self.is_available_in_website})
        if self.image:
            collection_vals.update({'image': {'attachment': self.image.decode('UTF-8')}})
        if self.collection_type == 'automated':
            collection_vals.update({'disjunctive': self.is_disjunctive})
            condition_list = []
            for condition_id in self.collection_condition_ids:
                condition_list.append({'column': condition_id.column, 'relation': condition_id.relation,
                                       'condition': condition_id.condition})
            collection_vals.update({'rules': condition_list})
        return collection_vals

    def update_odoo_collection(self, result):
        result_dict = result.to_dict()
        mk_listing_obj = self.env['mk.listing']
        handle = result_dict.get('handle', False)
        automated_collection_id = result_dict.get('id')
        shopify_product_list = self.sync_collection_products(result)
        mk_listing_ids = mk_listing_obj.search([('mk_id', 'in', shopify_product_list), ('mk_instance_id', '=', self.mk_instance_id.id)])
        self.write({'handle': handle,
                    'exported_in_shopify': True,
                    'shopify_collection_id': automated_collection_id,
                    'is_available_in_website': not self.is_available_in_website,
                    'mk_listing_ids': [(6, 0, mk_listing_ids.ids)],
                    'shopify_update_date': convert_shopify_datetime_to_utc(result_dict.get('updated_at')),
                    'shopify_publish_date': convert_shopify_datetime_to_utc(result_dict.get('published_at'))})
        return True

    def export_automated_collection_ts(self):
        if not self.collection_condition_ids:
            raise ValidationError(_("Please add at least one Condition in Automated Collection: {}".format(self.name)))
        new_collection = shopify.SmartCollection()
        collection_vals = self.prepare_collection_vals()
        try:
            result = new_collection.create(collection_vals)
        except Exception as e:
            raise ValidationError(_("Error while trying to Export Automated Collection, Error: {}".format(e)))
        if not result:
            return False
        self.update_odoo_collection(result)
        return True

    def export_manual_collection_ts(self):
        for collection_id in self:
            new_collection = shopify.CustomCollection()
            manual_collection = collection_id.prepare_collection_vals()
            template_list = []
            for listing_id in collection_id.mk_listing_ids:
                template_list.append({'product_id': listing_id.mk_id})
            manual_collection.update({'collects': template_list})
            try:
                result = new_collection.create(manual_collection)
            except Exception as e:
                raise ValidationError(_("Error while trying to Export Custom Collection, Error: {}".format(e)))
            if not result:
                continue
            collection_id.update_odoo_collection(result)
        return True

    def sync_automate_collection_product(self):
        mk_listing_obj = self.env['mk.listing']
        self.mk_instance_id.connection_to_shopify()
        if self.collection_type == 'automated':
            shopify_collection = shopify.SmartCollection.find(self.shopify_collection_id)
            shopify_product_list = self.sync_collection_products(shopify_collection)
            mk_listing_ids = mk_listing_obj.search([('mk_id', 'in', shopify_product_list), ('mk_instance_id', '=', self.mk_instance_id.id)])
            self.write({'mk_listing_ids': [(6, 0, mk_listing_ids.ids)]})
        return True

    def prepare_update_collection_vals(self, new_collection):
        new_collection.title = self.name
        if self.description:
            new_collection.body_html = self.description
        if self.template_suffix:
            new_collection.template_suffix = self.template_suffix
        if self.sort_order:
            new_collection.sort_order = self.sort_order
        if self.is_available_in_website:
            new_collection.published = self.is_available_in_website
        if self.image:
            new_collection.image = {'attachment': self.image.decode('UTF-8')}
        if self.collection_type == 'automated':
            new_collection.disjunctive = self.is_disjunctive
            condition_list = []
            for condition_id in self.collection_condition_ids:
                condition_list.append({'column': condition_id.column, 'relation': condition_id.relation, 'condition': condition_id.condition})
            new_collection.rules = condition_list
        return new_collection

    def update_automated_collection_ts(self):
        new_collection = shopify.SmartCollection().find(self.shopify_collection_id)
        if not new_collection:
            raise ValidationError(_("Cannot find Automated Collection: {} in Shopify".format(self.name)))

        new_collection = self.prepare_update_collection_vals(new_collection)
        new_collection.save()
        self.update_odoo_collection(new_collection)
        return True

    def get_existing_products(self, new_collection):
        products = new_collection.products()
        existing_product_list = [str(product.id) for product in products]
        return existing_product_list

    def update_manual_collection_ts(self):
        new_collection = shopify.CustomCollection().find(self.shopify_collection_id)
        if not new_collection:
            raise ValidationError(_("Cannot find Manual Collection: {} in Shopify".format(self.name)))

        new_collection = self.prepare_update_collection_vals(new_collection)
        odoo_templates_list, collection_product_list = [], []
        existing_collection_products = self.get_existing_products(new_collection)
        for listing_id in self.mk_listing_ids:
            odoo_templates_list.append(listing_id.mk_id)
            if listing_id.mk_id not in existing_collection_products:
                collection_product_list.append({'product_id': listing_id.mk_id})
        new_collection.collects = collection_product_list
        new_collection.save()
        remove_templates = list(set(existing_collection_products) - set(odoo_templates_list))
        for template in remove_templates:
            if template not in odoo_templates_list:
                new_collection.remove_product(shopify.Product().find(template))
        self.update_odoo_collection(new_collection)
        return True

    def export_update_collection_to_shopify_ts(self):
        need_to_export = self.filtered(lambda collection: not collection.exported_in_shopify)
        need_to_update = self.filtered(lambda collection: collection.exported_in_shopify)
        need_to_export and need_to_export.export_collection_to_shopify_ts()
        need_to_update and need_to_update.update_collection_to_shopify_ts()
        return True

    def export_collection_to_shopify_ts(self):
        for collection in self:
            mk_instance_id = collection.mk_instance_id
            mk_instance_id.connection_to_shopify()
            if collection.collection_type == 'automated':
                collection.export_automated_collection_ts()

            if collection.collection_type == 'manual':
                collection.export_manual_collection_ts()
        return True

    def update_collection_to_shopify_ts(self):
        for collection in self:
            mk_instance_id = collection.mk_instance_id
            mk_instance_id.connection_to_shopify()
            if collection.collection_type == 'automated':
                collection.update_automated_collection_ts()

            if collection.collection_type == 'manual':
                collection.update_manual_collection_ts()
        return True
