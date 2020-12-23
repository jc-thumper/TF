import time
import base64
import pprint
import requests
from .. import shopify
from datetime import timedelta
import urllib.parse as urlparse
from odoo import models, fields, tools, _
from .misc import convert_shopify_datetime_to_utc
from odoo.exceptions import AccessError, UserError

INVENTORY_MANAGEMENT = [('shopify', 'Track Quantity'), ('dont_track', 'Dont track Inventory')]
FULFILLMENT_SERVICE = [('manual', 'Manual'), ('shopify', 'shopify'), ('gift_card', 'Gift Card')]


class MkListing(models.Model):
    _inherit = "mk.listing"

    continue_selling = fields.Boolean("Continue selling when out of stock?", default=False)
    inventory_management = fields.Selection(INVENTORY_MANAGEMENT, default='shopify')
    fulfillment_service = fields.Selection(FULFILLMENT_SERVICE, default='manual')
    tag_ids = fields.Many2many("shopify.tags.ts", "shopify_tags_ts_rel", "product_tmpl_id", "tag_id", "Shopify Tags")
    is_taxable = fields.Boolean("Taxable", default=False)
    shopify_image_ids = fields.One2many('shopify.product.image.ts', 'mk_listing_id', 'Shopify Images')
    collection_id = fields.One2many("shopify.collection.ts", "mk_listing_ids", "Collections")

    def publish_product_in_shopify(self):
        mk_instance_id = self.mk_instance_id
        mk_instance_id.connection_to_shopify()
        if self.mk_id:
            try:
                shopify_product = shopify.Product.find(self.mk_id)
                if shopify_product:
                    shopify_product.id = self.mk_id
                    shopify_product.published = 'true'
                    published_at = fields.Datetime.now()
                    published_at = published_at.strftime("%Y-%m-%dT%H:%M:%S")
                    shopify_product.published_at = published_at
                    result = shopify_product.save()
                    if result:
                        result_dict = shopify_product.to_dict()

                        updated_at = convert_shopify_datetime_to_utc(result_dict.get('updated_at'))
                        published_at = convert_shopify_datetime_to_utc(result_dict.get('published_at'))
                        self.write({'listing_publish_date': published_at,
                                    'is_published': True,
                                    'listing_update_date': updated_at})
            except Exception as e:
                if not self.mk_id:
                    log_message = "Shopify Product {} is not found in Shopify while trying to Publish Product.".format(self.mk_id)
                    raise ValueError(_(log_message))
                else:
                    log_message = e
                    raise ValueError(_(log_message))

        return True

    def unpublish_product_in_shopify(self):
        self.mk_instance_id.connection_to_shopify()
        if self.mk_id:
            shopify_product = shopify.Product.find(self.mk_id)
            if shopify_product:
                shopify_product.id = self.mk_id
                shopify_product.published_at = None
                shopify_product.published = 'false'
                result = shopify_product.save()

                if result:
                    result_dict = shopify_product.to_dict()
                    updated_at = convert_shopify_datetime_to_utc(result_dict.get('updated_at', ''))
                    self.write({'listing_update_date': updated_at,
                                'listing_publish_date': False,
                                'is_published': False})
        return True

    def shopify_published(self):
        if not self.is_published:
            self.publish_product_in_shopify()
        else:
            self.unpublish_product_in_shopify()
        return True

    def fetch_all_shopify_products(self, mk_instance_id):
        try:
            shopify_product_list, api_limit, page_info = [], mk_instance_id.api_limit or 250, False
            while 1:
                if mk_instance_id.last_listing_import_date:
                    if page_info:
                        page_wise_product_list = shopify.Product().find(limit=api_limit, page_info=page_info)
                    else:
                        page_wise_product_list = shopify.Product().find(updated_at_min=mk_instance_id.last_listing_import_date, limit=api_limit)
                else:
                    if page_info:
                        page_wise_product_list = shopify.Product().find(limit=api_limit, page_info=page_info)
                    else:
                        page_wise_product_list = shopify.Product().find(limit=api_limit)
                page_url = page_wise_product_list.next_page_url
                parsed = urlparse.parse_qs(page_url)
                page_info = parsed.get('page_info', False) and parsed.get('page_info', False)[0] or False
                shopify_product_list += page_wise_product_list
                if not page_info:
                    break
            return shopify_product_list
        except Exception as e:
            raise AccessError(e)

    def get_product_category(self, shopify_product_type):
        category_obj = self.env['product.category']
        product_category_id = category_obj.search([('name', '=', shopify_product_type)], limit=1)
        if not product_category_id:
            product_category_id = category_obj.create({'name': shopify_product_type})
        return product_category_id

    def prepare_attribute_line_vals(self, shopify_product_dict):
        product_attribute_obj = self.env['product.attribute']
        product_attribute_value_obj = self.env['product.attribute.value']
        attribute_line_vals = []
        shopify_variant_list = shopify_product_dict.get("variants")
        if len(shopify_variant_list) > 1:
            for product_attribute_dict in shopify_product_dict.get("options", ""):
                attribute_name = product_attribute_dict.get("name", "")
                attribute_values = product_attribute_dict.get('values', '')
                product_attribute_id = product_attribute_obj.search([("name", "=ilike", attribute_name)], limit=1)
                if not product_attribute_id:
                    product_attribute_id = product_attribute_obj.create({"name": attribute_name})

                product_attribute_value_id_list = []
                for attribute_value in attribute_values:
                    attrib_value = product_attribute_value_obj.search([("attribute_id", "=", product_attribute_id.id), ("name", "=ilike", attribute_value)], limit=1)
                    if not attrib_value:
                        attrib_value = product_attribute_value_obj.with_context(active_id=False).create({"attribute_id": product_attribute_id.id, "name": attribute_value})
                    product_attribute_value_id_list.append(attrib_value.id)

                if product_attribute_value_id_list:
                    attribute_line_ids_data = [0, False, {"attribute_id": product_attribute_id.id, "value_ids": [[6, False, product_attribute_value_id_list]]}]
                    attribute_line_vals.append(attribute_line_ids_data)
        return attribute_line_vals

    def create_odoo_template_for_shopify_product(self, shopify_product_dict, existing_odoo_product, mk_instance_id, product_category_id, update_product_price):
        odoo_template_obj = self.env["product.template"]
        shopify_product_title = shopify_product_dict.get("title", "")
        shopify_variant_list = shopify_product_dict.get("variants")
        attribute_line_vals = self.prepare_attribute_line_vals(shopify_product_dict)
        product_template_vals = {
            'name': shopify_product_title,
            'type': 'product',
            'attribute_line_ids': attribute_line_vals,
            'description_sale': shopify_product_dict.get("description", "")
        }
        if mk_instance_id.is_update_odoo_product_category:
            product_template_vals.update({'categ_id': product_category_id.id})

        product_tmpl_id = odoo_template_obj.create(product_template_vals)
        if len(shopify_variant_list) > 1:
            # Adding SKU and Barcode in newly created variants according to marketplace variant's information.
            for variant_dict in shopify_variant_list:
                price = variant_dict.get("price", "")
                barcode = variant_dict.get('barcode')
                shopify_attribute_dict = {}
                for index, attribute_dict in enumerate(shopify_product_dict.get('options'), start=1):
                    attribute_value = variant_dict.get("option{}".format(index))
                    shopify_attribute_dict.update({attribute_dict.get('name'): attribute_value})
                # No need to check the attributes line of product template is well because we are creating the freash template with all possible attributes according to marketplace.
                # self.env['product.template.attribute.line'].create_or_update_ptal(shopify_attribute_dict, product_tmpl_id)
                odoo_product_id = self._find_odoo_product_from_marketplace_attribute(shopify_attribute_dict, product_tmpl_id)
                product_update_vals = {'default_code': variant_dict.get('sku')}
                if barcode:
                    product_update_vals.update({'barcode': barcode})
                # Note: Commented because we can't set the sales price for variant product in Odoo according to marketplace.
                # if price and update_product_price:
                #     if mk_instance_id.pricelist_id.currency_id.id == product_tmpl_id.company_id.currency_id.id:
                #         product_update_vals.update({'lst_price': float(price)})
                #     else:
                #         mk_instance_currency_id = mk_instance_id.pricelist_id.currency_id
                #         odoo_product_company_currency_id = product_tmpl_id.company_id.currency_id
                #         price_currency = mk_instance_currency_id._convert(float(price), odoo_product_company_currency_id, self.env.user.company_id, fields.Date.today())
                #         product_update_vals.update({'lst_price': price_currency})
                odoo_product_id.write(product_update_vals)
                existing_odoo_product.update({variant_dict.get('id'): odoo_product_id})
        else:
            product_tml_update_vals = {'default_code': shopify_variant_list[0].get('sku')}
            if shopify_variant_list[0].get('barcode'):
                product_tml_update_vals.update({'barcode': shopify_variant_list[0].get('barcode')})
            price = shopify_variant_list[0].get('price')
            if price and update_product_price:
                if mk_instance_id.pricelist_id.currency_id.id == product_tmpl_id.company_id.currency_id.id:
                    product_tml_update_vals.update({'list_price': float(price)})
                else:
                    mk_instance_currency_id = mk_instance_id.pricelist_id.currency_id
                    odoo_product_company_currency_id = product_tmpl_id.company_id.currency_id
                    price_currency = mk_instance_currency_id._convert(float(price), odoo_product_company_currency_id, self.env.user.company_id, fields.Date.today())
                    product_tml_update_vals.update({'list_price': price_currency})
            converted_weight = self.env['mk.listing']._marketplace_convert_weight(shopify_variant_list[0].get('weight'), shopify_variant_list[0].get('weight_unit'))
            if converted_weight and product_tmpl_id:
                product_tml_update_vals.update({'weight': converted_weight})
            product_tmpl_id.write(product_tml_update_vals)
            existing_odoo_product.update({shopify_variant_list[0].get('id'): product_tmpl_id.product_variant_ids})
        return product_tmpl_id

    def prepare_marketplace_listing_vals_for_shopify(self, mk_instance_id, shopify_product_dict, shopify_variant_dict, odoo_product_id, product_category_id):
        vals = {}
        mk_id = shopify_product_dict.get("id", "")
        shopify_product_tags = shopify_product_dict.get('tags')
        variant_taxable = shopify_product_dict.get("taxable", "")
        shopify_variant_list = shopify_product_dict.get("variants")
        shopify_product_title = shopify_product_dict.get("title", "")
        shopify_product_body_html = shopify_product_dict.get("body_html", "")
        shopify_product_updated_at = convert_shopify_datetime_to_utc(shopify_product_dict.get("updated_at", ""))
        shopify_product_created_at = convert_shopify_datetime_to_utc(shopify_product_dict.get("created_at", ""))
        shopify_product_published_at = convert_shopify_datetime_to_utc(shopify_product_dict.get("published_at", ""))
        variant_inventory_policy = shopify_variant_dict.get("inventory_policy", "")
        variant_fulfillment_service = shopify_variant_dict.get("fulfillment_service", "")
        variant_inventory_management = shopify_variant_dict.get("inventory_management", "")

        if variant_inventory_management == 'shopify':
            vals.update({'inventory_management': 'shopify'})
        else:
            vals.update({'inventory_management': 'dont_track'})

        if variant_inventory_policy == 'continue':
            vals.update({'continue_selling': True})

        vals.update(
            {'name': shopify_product_title,
             'product_category_id': product_category_id.id,
             'mk_instance_id': mk_instance_id.id,
             'product_tmpl_id': odoo_product_id.product_tmpl_id.id,
             'mk_id': mk_id,
             'listing_create_date': shopify_product_created_at,
             'listing_update_date': shopify_product_updated_at,
             'listing_publish_date': shopify_product_published_at,
             'fulfillment_service': variant_fulfillment_service,
             'is_taxable': variant_taxable,
             'description': shopify_product_body_html,
             'is_published': True if shopify_product_published_at else False,
             'is_listed': True,
             'number_of_variants_in_mk': len(shopify_variant_list)})

        shopify_tag_vals = self.prepage_tag_vals(shopify_product_tags)
        if shopify_tag_vals:
            vals.update(shopify_tag_vals)
        return vals

    def prepare_marketplace_listing_item_vals_for_shopify(self, shopify_product_dict, shopify_variant_dict, mk_instance_id, odoo_product_id, mk_listing_id):
        variant_title = shopify_variant_dict.get("title", "")
        variant_title = shopify_product_dict.get("title", "") if variant_title == 'Default Title' else variant_title
        variant_inventory_management = shopify_variant_dict.get("inventory_management", "")
        vals = {
            'name': variant_title,
            'product_id': odoo_product_id.id,
            'default_code': shopify_variant_dict.get("sku", ""),
            'mk_listing_id': mk_listing_id.id,
            'mk_id': shopify_variant_dict.get("id", ""),
            'mk_instance_id': mk_instance_id.id,
            'item_create_date': convert_shopify_datetime_to_utc(shopify_variant_dict.get("created_at", "")),
            'item_update_date': convert_shopify_datetime_to_utc(shopify_variant_dict.get("updated_at", "")),
            'is_listed': True,
            'inventory_item_id': shopify_variant_dict.get("inventory_item_id", ""),
            'continue_selling': shopify_variant_dict.get("inventory_policy", ""),
        }
        if variant_inventory_management == 'shopify':
            vals.update({'inventory_management': 'shopify'})
        else:
            vals.update({'inventory_management': 'dont_track'})
        return vals

    def prepage_tag_vals(self, shopify_product_tags):
        shopify_tag_obj = self.env['shopify.tags.ts']
        shopify_tag_list = []
        sequence = 1
        for tag in shopify_product_tags.split(','):
            if len(tag) < 1:
                continue
            shopify_tag_id = shopify_tag_obj.search([('name', '=', tag)], limit=1)
            if not shopify_tag_id:
                shopify_tag_id = shopify_tag_obj.create({'name': tag, 'sequence': sequence})
                sequence += 1
            shopify_tag_list.append(shopify_tag_id.id)
        return {'tag_ids': [(6, 0, shopify_tag_list)]}

    def sync_product_image_from_shopify(self, mk_instance_id, mk_listing_id, shopify_product_dict):
        shopify_image_response_vals = shopify_product_dict.get('images', {})
        mk_listing_image = self.env['mk.listing.image']
        mk_listing_item_obj = self.env['mk.listing.item']
        if not shopify_image_response_vals:
            mk_instance_id.connection_to_shopify()
            images = shopify.Image().find(product_id=mk_listing_id.mk_id)
            shopify_image_response_vals = [image.to_dict() for image in images]
        for image in shopify_image_response_vals:
            image_url = image.get('src')
            if image_url:
                variant_ids, shopify_image_id = image.get('variant_ids'), image.get('id')
                mk_listing_item_ids = mk_listing_item_obj.search([('mk_instance_id', '=', mk_instance_id.id), ('mk_id', 'in', variant_ids)])
                listing_image_id = mk_listing_image.search([('mk_id', '=', shopify_image_id)])
                image_binary = base64.b64encode(requests.get(image_url).content)
                vals = {
                    'name': mk_listing_id.name,
                    'mk_id': shopify_image_id,
                    'sequence': image.get('position'),
                    'image': image_binary,
                    'mk_listing_id': mk_listing_id.id,
                    'mk_listing_item_ids': [(6, 0, mk_listing_item_ids.ids)],
                }
                if listing_image_id:
                    listing_image_id.write(vals)
                else:
                    mk_listing_image.create(vals)

                for listing_item in mk_listing_item_ids:
                    listing_item.product_id.write({'image_1920': image_binary})

                if image.get('position') == 1:
                    mk_listing_id.product_tmpl_id.write({'image_1920': image_binary})
        return True

    def get_existing_mk_listing_and_odoo_product(self, shopify_variant_list, mk_instance_id):
        existing_mk_product = {}
        existing_odoo_product = {}
        odoo_product_template = self.env['product.template']
        for variant_dict in shopify_variant_list:
            odoo_product_id, listing_item_id = self.get_odoo_product_variant_and_listing_item(mk_instance_id, variant_dict.get("id", ""), variant_dict.get("barcode", ""),
                                                                                              variant_dict.get("sku", ""))
            if odoo_product_id:
                odoo_product_template |= odoo_product_id.product_tmpl_id
                existing_odoo_product.update({variant_dict.get("id"): odoo_product_id})
            elif listing_item_id and not odoo_product_id:
                existing_odoo_product.update({variant_dict.get("id"): listing_item_id.product_id})
            listing_item_id and existing_mk_product.update({variant_dict.get("id"): listing_item_id})
        return existing_mk_product, existing_odoo_product, odoo_product_template

    def create_update_shopify_product(self, shopify_product_dict, mk_instance_id, update_product_price=False, is_update_existing_products=True):
        mk_log_id = self.env.context.get('mk_log_id', False)
        queue_line_id = self.env.context.get('queue_line_id', False)
        mk_listing_item_obj = self.env['mk.listing.item']
        mk_id = shopify_product_dict.get("id", "")
        shopify_product_type = shopify_product_dict.get("product_type", "")
        shopify_variant_list = shopify_product_dict.get("variants")
        mk_listing_id = self.search([('mk_instance_id', '=', mk_instance_id.id), ('mk_id', '=', mk_id)])
        if not mk_listing_id and not is_update_existing_products:
            return False
        variant_sequence = 1
        listing_updated = False

        # Checking validation for marketplace product for duplicated SKU or Barcode before start importing.
        listing_item_validation_dict = {'name': shopify_product_dict.get('title'), 'id': shopify_product_dict.get('id'),
                                        'variants': [{'sku': variant_dict.get('sku'), 'barcode': variant_dict.get('barcode'), 'id': variant_dict.get('id')} for variant_dict in
                                                     shopify_product_dict.get('variants')]}
        validated, log_message = self.check_for_duplicate_sku_or_barcode_in_marketplace_product(mk_instance_id.sync_product_with, listing_item_validation_dict)
        if not validated:
            self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id,
                                                 mk_log_line_dict={'error': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
            return False
        existing_mk_product, existing_odoo_product, odoo_product_template = self.get_existing_mk_listing_and_odoo_product(shopify_variant_list, mk_instance_id)

        if len(odoo_product_template) > 1:
            log_message = "IMPORT LISTING: Found multiple Odoo Product ({}) For Shopify Product : {}.".format(','.join([x.name for x in odoo_product_template]),
                                                                                                              shopify_product_dict.get("title", ""))
            self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id,
                                                 mk_log_line_dict={'error': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
            return False

        validated, log_message = self.check_validation_for_import_product(mk_instance_id.sync_product_with, listing_item_validation_dict, odoo_product_template,
                                                                          existing_odoo_product, existing_mk_product)
        if not validated:
            self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id,
                                                 mk_log_line_dict={'error': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
            return False

        attribute_line_vals = self.prepare_attribute_line_vals(shopify_product_dict)
        if len(shopify_product_dict.get('variants')) > 1 and (mk_listing_id or odoo_product_template):
            if not odoo_product_template:
                odoo_product_template = mk_listing_id.product_tmpl_id
            # if not odoo_product_template.attribute_line_ids:
            for variant_dict in shopify_variant_list:
                shopify_attribute_dict = {}
                variant_sku = variant_dict.get("sku") or False
                variant_barcode = variant_dict.get("barcode") or False
                for index, attribute_dict in enumerate(shopify_product_dict.get('options'), start=1):
                    attribute_value = variant_dict.get("option{}".format(index))
                    shopify_attribute_dict.update({attribute_dict.get('name'): attribute_value})
                self.env['product.template.attribute.line'].create_or_update_ptal(shopify_attribute_dict, odoo_product_template, attribute_line_vals)
                odoo_product_id = self._find_odoo_product_from_marketplace_attribute(shopify_attribute_dict, odoo_product_template)
                if odoo_product_id:
                    odoo_prod_vals = {}
                    if not odoo_product_id.default_code:
                        odoo_prod_vals = {'default_code': variant_sku}
                    if not odoo_product_id.barcode and variant_barcode:
                        odoo_prod_vals.update({'barcode': variant_barcode})
                    if odoo_prod_vals:
                        odoo_product_id.write(odoo_prod_vals)

        existing_mk_product, existing_odoo_product, odoo_product_template = self.get_existing_mk_listing_and_odoo_product(shopify_variant_list, mk_instance_id)

        product_category_id = self.get_product_category(shopify_product_type)
        for variant_dict in shopify_variant_list:
            variant_id = variant_dict.get("id", "")
            variant_sku = variant_dict.get("sku") or False
            variant_barcode = variant_dict.get("barcode") or False
            variant_price = variant_dict.get('price')
            listing_item_id = existing_mk_product.get(variant_id, False)
            odoo_product_id = existing_odoo_product.get(variant_id, False)
            if not listing_item_id:
                if not mk_listing_id:
                    if not odoo_product_template and not mk_instance_id.is_create_products:
                        log_message = "IMPORT LISTING: Odoo Product not found for Shopify Product : {} and SKU: {} and Barcode : {}".format(shopify_product_dict.get("title", ""),
                                                                                                                                            variant_sku, variant_barcode)
                        self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict={
                            'error': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
                        break
                    if not odoo_product_template:
                        odoo_product_template = self.create_odoo_template_for_shopify_product(shopify_product_dict, existing_odoo_product, mk_instance_id, product_category_id,
                                                                                              update_product_price)
                        odoo_product_id = existing_odoo_product.get(variant_id, False)
                    shopify_product_template_vals = self.prepare_marketplace_listing_vals_for_shopify(mk_instance_id, shopify_product_dict, variant_dict, odoo_product_id,
                                                                                                      product_category_id)
                    mk_listing_id = self.create(shopify_product_template_vals)
                    log_message = 'IMPORT LISTING: {} successfully created'.format(mk_listing_id.name)
                    self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict={
                        'success': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
                if not odoo_product_id:
                    if not mk_instance_id.is_create_products:
                        log_message = "IMPORT LISTING ITEM: Odoo Product Variant not found for Shopify Product Variant : {} and SKU: {} and Barcode : {}".format(
                            shopify_product_dict.get("title", ""), variant_sku, variant_barcode)
                        self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict={
                            'error': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
                        break
                    if odoo_product_template.attribute_line_ids:
                        shopify_attribute_ids = self.env["product.attribute"]
                        odoo_attributes = odoo_product_template.attribute_line_ids.attribute_id
                        for attribute in shopify_product_dict.get('options'):
                            attribute_id = self.env["product.attribute"].search([('name', '=ilike', attribute["name"]), ('create_variant', '=', 'always')], limit=1)
                            shopify_attribute_ids |= attribute_id
                        if odoo_attributes != shopify_attribute_ids or len(odoo_attributes) != len(shopify_product_dict.get('options')):
                            log_message = "IMPORT LISTING ITEM: Odoo attribute ({}) isn't matching with Shopify attribute ({}) for Shopify Product : {}".format(
                                ','.join(odoo_attributes.mapped('name')), ','.join(shopify_attribute_ids.mapped('name')), shopify_product_dict.get("title", ""))
                            self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict={
                                'error': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
                            break
                        else:
                            shopify_attribute_dict = {}
                            for index, attribute_dict in enumerate(shopify_product_dict.get('options'), start=1):
                                attribute_value = variant_dict.get("option{}".format(index))
                                shopify_attribute_dict.update({attribute_dict.get('name'): attribute_value})
                            self.env['product.template.attribute.line'].create_or_update_ptal(shopify_attribute_dict, odoo_product_template, attribute_line_vals)
                            odoo_product_id = self._find_odoo_product_from_marketplace_attribute(shopify_attribute_dict, odoo_product_template)
                            odoo_prod_vals = {'default_code': variant_sku}
                            if variant_barcode:
                                odoo_prod_vals.update({'barcode': variant_barcode})
                            odoo_product_id.write(odoo_prod_vals)
                mk_listing_item_vals = self.prepare_marketplace_listing_item_vals_for_shopify(shopify_product_dict, variant_dict, mk_instance_id, odoo_product_id, mk_listing_id)
                mk_listing_item_vals.update({'sequence': variant_sequence})
                converted_weight = mk_listing_id._marketplace_convert_weight(variant_dict.get('weight'), variant_dict.get('weight_unit'))
                if converted_weight and odoo_product_id and not odoo_product_id.weight:
                    odoo_product_id.weight = converted_weight
                listing_item_id = mk_listing_item_obj.create(mk_listing_item_vals)
                variant_sequence += 1
                self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict={'success': [
                    {'log_message': 'IMPORT LISTING ITEM: {} ({}) successfully created'.format(mk_listing_id.name, listing_item_id.mk_id),
                     'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
            else:
                if not listing_updated:
                    listing_vals = self.prepare_marketplace_listing_vals_for_shopify(mk_instance_id, shopify_product_dict, variant_dict,
                                                                                     odoo_product_id or listing_item_id.product_id, product_category_id)
                    mk_listing_id.write(listing_vals)
                    listing_updated = True
                mk_listing_item_vals = self.prepare_marketplace_listing_item_vals_for_shopify(shopify_product_dict, variant_dict, mk_instance_id,
                                                                                              odoo_product_id or listing_item_id.product_id, mk_listing_id)
                listing_item_id.write(mk_listing_item_vals)
                converted_weight = mk_listing_id._marketplace_convert_weight(variant_dict.get('weight'), variant_dict.get('weight_unit'))
                if converted_weight and odoo_product_id and not odoo_product_id.weight:
                    odoo_product_id.weight = converted_weight
                variant_sequence = variant_sequence + 1
                self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict={'success': [
                    {'log_message': 'IMPORT LISTING: {} successfully updated'.format(mk_listing_id.name), 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
            listing_item_id.create_or_update_pricelist_item(float(variant_price))
        if len(shopify_product_dict.get('variants')) != mk_listing_id.item_count:
            mk_id_list = [str(variant_dict.get('id')) for variant_dict in shopify_product_dict.get('variants')]
            mk_listing_id.remove_extra_listing_item(mk_id_list)
        return mk_listing_id

    def shopify_import_listings(self, mk_instance_id, mk_listing_id=False):
        mk_instance_id.connection_to_shopify()
        if mk_listing_id:
            proudct_list = []
            mk_log_line_dict = self.env.context.get('mk_log_line_dict', {'error': [], 'success': []})
            mk_log_id = self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, operation_type='import')
            for product in ''.join(mk_listing_id.split()).split(','):
                proudct_list.append(shopify.Product().find(product))
            for shopify_product in proudct_list:
                shopify_product_dict = shopify_product.to_dict()
                mk_listing_id = self.with_context(mk_log_line_dict=mk_log_line_dict, mk_log_id=mk_log_id).create_update_shopify_product(shopify_product_dict, mk_instance_id,
                                                                                                                                        update_product_price=True)
                if mk_listing_id and mk_instance_id.is_sync_images:
                    self.sync_product_image_from_shopify(mk_instance_id, mk_listing_id, shopify_product_dict)
            if mk_log_line_dict.get('error'):
                raise UserError(_("Found problem during Import listing, Details are below.\n{}".format(
                    ',\n'.join([error_dict.get('log_message') for error_dict in mk_log_line_dict.get('error')]))))
            if not mk_log_id.log_line_ids and not self.env.context.get('log_id', False):
                mk_log_id.unlink()
            return mk_listing_id
        else:
            shopify_product_list = self.fetch_all_shopify_products(mk_instance_id)

        if shopify_product_list:
            batch_size = mk_instance_id.queue_batch_limit or 100
            for shopify_products in tools.split_every(batch_size, shopify_product_list):
                queue_id = mk_instance_id.action_create_queue(type='product')
                for product in shopify_products:
                    shopify_product_dict = product.to_dict()
                    name = shopify_product_dict.get('title', '') or ''
                    line_vals = {
                        'mk_id': shopify_product_dict.get('id') or '',
                        'state': 'draft',
                        'name': name.strip(),
                        'data_to_process': pprint.pformat(shopify_product_dict),
                        'mk_instance_id': mk_instance_id.id,
                    }
                    queue_id.action_create_queue_lines(line_vals)
        mk_instance_id.last_listing_import_date = fields.Datetime.now()
        return True

    def cancel_older_adjustments(self):
        inventory_adjustments_ids = self.env['stock.inventory'].search([('is_shopify_adjustment', '=', True), ('state', '!=', 'done')])
        for adjustment_id in inventory_adjustments_ids:
            if not adjustment_id.state == 'cancel':
                adjustment_id.action_cancel_draft()
                adjustment_id.write({'state': 'cancel'})
        return True

    def prepare_location_wise_inventory_level(self, shopify_inventory_levels):
        location_wise_inventory_dict = {}
        for inventory_level in shopify_inventory_levels:
            inventory_level = inventory_level.to_dict()
            location_mk_id = inventory_level.get('location_id')
            if location_mk_id in location_wise_inventory_dict:
                location_wise_inventory_dict[location_mk_id].append(inventory_level)
            else:
                location_wise_inventory_dict.update({location_mk_id: [inventory_level]})
        return location_wise_inventory_dict

    def create_process_inventory_adjustment(self, mk_instance_id, shopify_location_id, inventory_line_list, product_variant_ids):
        inventory_adjustment_vals = {
            'is_shopify_adjustment': True,
            'location_ids': shopify_location_id.location_id.ids,
            'name': 'SHOPIFY({}): Inventory for Account {} And Location {}'.format(fields.Date.to_string(fields.Date.today()), mk_instance_id.name, shopify_location_id.name)}
        if inventory_adjustment_vals and inventory_line_list:
            inventory_adjustment_vals.update({'line_ids': inventory_line_list,
                                              'product_ids': [(6, 0, product_variant_ids.ids)]})
            inventory_adjustment_id = self.env['stock.inventory'].create(inventory_adjustment_vals)
            inventory_adjustment_id.action_start()
            if mk_instance_id.is_validate_adjustment:
                inventory_adjustment_id.action_validate()
            return inventory_adjustment_id
        return False

    def prepare_inv_adjustment_lines(self, inventory_level_list, mk_instance_id, shopify_location_id):
        product_variant_ids, inventory_line_list = self.env['product.product'], []
        for inventory_level in inventory_level_list:
            inventory_item_id = inventory_level.get('inventory_item_id')
            qty = inventory_level.get('available', 0) or 0
            shopify_product = self.env['mk.listing.item'].search(
                [('product_id.type', '!=', 'service'), ('is_listed', '=', True), ('inventory_item_id', '=', inventory_item_id),
                 ('mk_instance_id', '=', mk_instance_id.id)], limit=1)
            if shopify_product:
                odoo_product_id = shopify_product.product_id
                if not any([line[2].get('product_id') == odoo_product_id.id for line in inventory_line_list]):
                    product_variant_ids += odoo_product_id
                    inventory_line_list.append((0, 0, {"product_id": odoo_product_id.id,
                                                       "location_id": shopify_location_id.location_id.id,
                                                       "product_qty": qty if qty > 0 else 0}))
        return inventory_line_list, product_variant_ids

    def fetch_all_shopify_inventory_level(self, mk_instance_id, shopify_loc_mk_ids):
        try:
            shopify_inventory_level_list, page_info = [], False
            while 1:
                if mk_instance_id.last_stock_import_date:
                    if page_info:
                        page_wise_inventory_list = shopify.InventoryLevel().find(page_info=page_info)
                    else:
                        page_wise_inventory_list = shopify.InventoryLevel().find(updated_at_min=mk_instance_id.last_stock_import_date, location_ids=','.join(shopify_loc_mk_ids))
                else:
                    if page_info:
                        page_wise_inventory_list = shopify.InventoryLevel().find(page_info=page_info)
                    else:
                        page_wise_inventory_list = shopify.InventoryLevel().find(location_ids=','.join(shopify_loc_mk_ids))
                page_url = page_wise_inventory_list.next_page_url
                parsed = urlparse.parse_qs(page_url)
                page_info = parsed.get('page_info', False) and parsed.get('page_info', False)[0] or False
                shopify_inventory_level_list += page_wise_inventory_list
                if not page_info:
                    break
            return shopify_inventory_level_list
        except Exception as e:
            raise AccessError(e)

    def shopify_import_stock(self, mk_instance_id):
        mk_log_id = self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, operation_type='import')
        product_template_ids = self.search([('mk_instance_id', '=', mk_instance_id.id), ('is_listed', '=', True)])
        self.cancel_older_adjustments()
        if product_template_ids:
            mk_instance_id.connection_to_shopify()
            location_ids = self.env['shopify.location.ts'].search([('mk_instance_id', '=', mk_instance_id.id)])
            if not location_ids:
                log_message = "IMPORT STOCK: No location found for Shopify Instance {} at the time of Import stock!".format(mk_instance_id.name)
                self.env['mk.log'].create_update_log(mk_log_id=mk_log_id, mk_log_line_dict={'success': [{'log_message': log_message}]})
                return False

            for location_id in location_ids:
                warehouse_id = location_id.warehouse_id or False
                odoo_location_id = location_id.location_id or False
                if not warehouse_id or not odoo_location_id:
                    log_message = "IMPORT STOCK: Warehouse / Location is not set for Shopify Location {}. Please set from Marketplace > Shopify > Locations".format(
                        location_id.name)
                    self.env['mk.log'].create_update_log(mk_log_id=mk_log_id, mk_log_line_dict={'success': [{'log_message': log_message}]})
                    return False

            shopify_loc_mk_ids = location_ids.mapped('shopify_location_id')
            shopify_inventory_levels = self.fetch_all_shopify_inventory_level(mk_instance_id, shopify_loc_mk_ids)
            location_wise_inventory_dict = self.prepare_location_wise_inventory_level(shopify_inventory_levels)

            for location_mk_id, inventory_level_list in location_wise_inventory_dict.items():
                try:
                    shopify_location_id = self.env['shopify.location.ts'].search([('shopify_location_id', '=', location_mk_id)])
                    inventory_line_list, product_variant_ids = self.prepare_inv_adjustment_lines(inventory_level_list, mk_instance_id, shopify_location_id)
                    inventory_adjustment_id = self.create_process_inventory_adjustment(mk_instance_id, shopify_location_id, inventory_line_list, product_variant_ids)
                    if inventory_adjustment_id:
                        log_message = "IMPORT STOCK: Stock imported Successfully. Check Inventory Adjustment: {}".format(inventory_adjustment_id.name)
                        self.env['mk.log'].create_update_log(mk_log_id=mk_log_id, mk_log_line_dict={'success': [{'log_message': log_message}]})
                except Exception as e:
                    log_message = "IMPORT STOCK: Error while Import Stock. ERROR: {}".format(e)
                    self.env['mk.log'].create_update_log(mk_log_id=mk_log_id, mk_log_line_dict={'success': [{'log_message': log_message}]})
                    return False
            if not mk_log_id.log_line_ids and not self.env.context.get('log_id', False):
                mk_log_id.unlink()
            mk_instance_id.last_stock_import_date = fields.Datetime.now()
        return True

    def update_shopify_variant_ts(self, new_shopify_product, operation_wizard):
        option_list, variant_list = ['option1', 'option2', 'option3'], []
        is_set_price = operation_wizard.is_set_price
        for listing_item_id in self.listing_item_ids:
            variant_vals = {}
            if operation_wizard.is_update_product:
                option_index = 0
                variant_vals.update({'title': listing_item_id.name,
                                     'grams': int(listing_item_id.product_id.weight * 1000),
                                     'weight': listing_item_id.product_id.weight,
                                     'weight_unit': 'kg',
                                     'sku': listing_item_id.default_code,
                                     'taxable': self.is_taxable and 'true' or 'false', })
                if listing_item_id.product_id.barcode:
                    variant_vals.update({'barcode': listing_item_id.product_id.barcode})
                if self.fulfillment_service == 'manual':
                    variant_vals.update({'fulfillment_service': 'manual'})
                if self.inventory_management == 'shopify':
                    variant_vals.update({'inventory_management': self.inventory_management})
                if self.continue_selling:
                    variant_vals.update({'inventory_policy': 'continue'})
                for atts in listing_item_id.product_id.product_template_attribute_value_ids:
                    variant_vals.update({option_list[option_index]: atts.name})
                    option_index += 1
                    if option_index > 2:
                        break
            if is_set_price:
                variant_price = self.mk_instance_id.pricelist_id.with_context(uom=listing_item_id.product_id.uom_id.id).get_product_price(listing_item_id.product_id, 1.0, False)
                variant_vals.update({'price': variant_price, 'id': listing_item_id.mk_id})
            if variant_vals:
                variant_list.append(variant_vals)
        if variant_list:
            new_shopify_product.variants = variant_list
        return variant_list

    def update_shopify_options_ts(self, new_shopify_product):
        self.ensure_one()
        attribute_list = []
        product_attribute_line_obj, attribute_position = self.env['product.template.attribute.line'], 1
        attribute_line_ids = self.product_tmpl_id.attribute_line_ids
        for attribute_line_id in attribute_line_ids:
            attribute_id = attribute_line_id.attribute_id
            attribute_name_list = attribute_line_id.value_ids.mapped('name')
            attribute_list.append({'name': attribute_id.name, 'values': attribute_name_list, 'position': attribute_position})
            attribute_position += 1
            if attribute_position > 3:
                break
        if attribute_list:
            new_shopify_product.options = attribute_list
        return attribute_list

    def update_odoo_shopify_product(self, new_shopify_product):
        self.ensure_one()
        shopify_product_dict = new_shopify_product.to_dict()
        self.write(
            {'listing_publish_date': convert_shopify_datetime_to_utc(shopify_product_dict.get("published_at")),
             'listing_update_date': convert_shopify_datetime_to_utc(shopify_product_dict.get("updated_at")),
             'listing_create_date': convert_shopify_datetime_to_utc(shopify_product_dict.get("created_at")),
             'mk_id': shopify_product_dict.get("id"),
             'is_listed': True,
             'is_published': True if shopify_product_dict.get("published_at", False) else False,
             'number_of_variants_in_mk': len(shopify_product_dict.get('variants'))})
        for shopify_variant_dict in shopify_product_dict.get('variants', []):
            shopify_variant_id = self.env['mk.listing.item'].search([('default_code', '=', shopify_variant_dict.get('sku')), ('mk_instance_id', '=', self.mk_instance_id.id)])
            if shopify_variant_id:
                shopify_variant_id.write({'mk_id': shopify_variant_dict.get('id'),
                                          'inventory_item_id': shopify_variant_dict.get('inventory_item_id'),
                                          'is_listed': True,
                                          'item_update_date': convert_shopify_datetime_to_utc(shopify_variant_dict.get("updated_at")),
                                          'item_create_date': convert_shopify_datetime_to_utc(shopify_variant_dict.get("created_at"))})

        return True

    def update_existing_shopify_images(self, mk_id):
        # TODO: alt text isn't updating to Shopify need to check in detail.
        shopify_image = False
        shopify_images = shopify.Image().find(product_id=self.mk_id)
        if not shopify_images:
            return False
        for shopify_image in shopify_images:
            if int(mk_id) == shopify_image.id:
                shopify_image = shopify_image
                break
        return shopify_image

    def update_shopify_product_image_ts(self):
        self.ensure_one()

        # Deleting listing images in Shopify if no images available in Odoo.
        shopify_images = shopify.Image().find(product_id=self.mk_id)
        if not self.image_ids and shopify_images:
            for images in shopify_images:
                images.destroy()
            return False

        # Adding and updating Shopify Images
        for image_id in self.image_ids:
            if not image_id.mk_id and image_id.image:
                shopify_image = shopify.Image()
                shopify_image.product_id = self.mk_id
                shopify_image.position = image_id.sequence
                shopify_image.attachment = image_id.image.decode('UTF-8')
                shopify_image.alt = image_id.shopify_alt_text or ''
                shopify_image.variant_ids = image_id.mk_listing_item_ids.mapped('mk_id')
                response = shopify_image.save()
                if response:
                    image_id.mk_id = shopify_image.id
            else:
                for shopify_image in shopify_images:
                    if int(image_id.mk_id) == shopify_image.id:
                        shopify_image.id = shopify_image.id
                        shopify_image.position = image_id.sequence
                        shopify_image.alt = image_id.shopify_alt_text or ''
                        shopify_image.attachment = image_id.image.decode('UTF-8')
                        shopify_image.save()
                        break

        # Deleting listing images in Shopify that will not exist in Odoo.
        odoo_shopify_images = self.image_ids.mapped('mk_id')
        for shop_image in shopify_images:
            if not str(shop_image.id) in odoo_shopify_images:
                shop_image.destroy()
        return True

    def prepare_update_vals_for_shopify_template(self, new_shopify_product):
        self.ensure_one()
        if self.description:
            new_shopify_product.body_html = self.description
        new_shopify_product.title = self.name
        new_shopify_product.tags = [tag.name for tag in self.tag_ids]
        new_shopify_product.product_type = self.product_category_id.name
        if self.product_tmpl_id.seller_ids:
            new_shopify_product.vendor = self.product_tmpl_id.seller_ids[0].display_name
        return new_shopify_product

    def shopify_export_listing_to_mk(self, operation_wizard):
        self.ensure_one()
        if self.mapped('listing_item_ids').filtered(lambda x: not x.default_code):
            raise UserError(_("Please set Internal Reference in Variant of Product Name {}".format(self.name)))
        if operation_wizard.is_set_quantity:
            # Added this validation because if user forgot to set Warehouse and Stock Location in the Shopify Location then as per the code sequence product will be created but
            # while going to export qty it will raise the error and Odoo product didn't updated even after it is created in Shopify.
            location_ids = self.env['shopify.location.ts'].search([('mk_instance_id', '=', self.mk_instance_id.id)])
            for shopify_location_id in location_ids:
                warehouse_id = shopify_location_id.warehouse_id or False
                if not warehouse_id:
                    raise UserError(
                        _("Please set Warehouse and Location in the Shopify Location {}. Marketplaces > Shopify > Configuration > Locations ".format(shopify_location_id.name)))
        self.mk_instance_id.connection_to_shopify()
        new_shopify_product = shopify.Product()
        new_shopify_product.published = 'true' if operation_wizard.is_publish_in_store else 'false'
        self.prepare_update_vals_for_shopify_template(new_shopify_product)

        self.update_shopify_variant_ts(new_shopify_product, operation_wizard)
        self.update_shopify_options_ts(new_shopify_product)

        result = new_shopify_product.save()
        if result:
            self.update_odoo_shopify_product(new_shopify_product)
        if operation_wizard.is_set_images:
            self.update_shopify_product_image_ts()
        if operation_wizard.is_set_quantity:
            self.update_location_wise_qty_in_shopify()
        self._cr.commit()
        return True

    def shopify_update_listing_to_mk(self, operation_wizard):
        self.ensure_one()
        result = False
        self.mk_instance_id.connection_to_shopify()
        try:
            shopify_product = shopify.Product().find(self.mk_id)
        except Exception as e:
            if e.code == 429:
                time.sleep(3)
                shopify_product = shopify.Product().find(self.mk_id)
            else:
                raise AccessError(_("Error while trying to find Shopify Template {} ERROR:{}".format(self.mk_id, e)))

        if operation_wizard.is_set_quantity:
            self.update_location_wise_qty_in_shopify()

        if operation_wizard.is_update_product:
            self.prepare_update_vals_for_shopify_template(shopify_product)

        self.update_shopify_variant_ts(shopify_product, operation_wizard)
        if operation_wizard.is_update_product:
            self.update_shopify_options_ts(shopify_product)
        if not operation_wizard.is_set_quantity:
            result = shopify_product.save()
        if not self.is_published and operation_wizard.is_publish_in_store:
            shopify_product.published = 'true'
            published_at = fields.Datetime.now()
            published_at = published_at.strftime("%Y-%m-%dT%H:%M:%S")
            shopify_product.published_at = published_at
            result = shopify_product.save()
        if result:
            self.update_odoo_shopify_product(shopify_product)
        if operation_wizard.is_set_images:
            self.update_shopify_product_image_ts()
            # shopify_product.save() update_shopify_product_image_ts method create image in shopify but while save shopify_product
            # newly created image will be deleted and seems nothing is changed.
        return True

    def update_location_wise_qty_in_shopify(self):
        self.ensure_one()
        location_ids = self.env['shopify.location.ts'].search([('mk_instance_id', '=', self.mk_instance_id.id)])
        for shopify_location_id in location_ids:
            warehouse_id = shopify_location_id.warehouse_id or False
            if not warehouse_id:
                raise UserError(
                    _("Please set Warehouse and Location in the Shopify Location {}. Marketplaces > Shopify > Configuration > Locations ".format(shopify_location_id.name)))
            for shopify_variant_id in self.listing_item_ids:
                if shopify_variant_id.product_id.type == 'product' and not shopify_variant_id.inventory_item_id:
                    continue
                if shopify_variant_id.inventory_management == 'dont_track':
                    continue
                variant_quantity = shopify_variant_id.product_id.get_product_stock(shopify_variant_id.export_qty_type, shopify_variant_id.export_qty_value, warehouse_id,
                                                                                   self.mk_instance_id.stock_field_id.name)
                try:
                    shopify.InventoryLevel.set(shopify_location_id.shopify_location_id, shopify_variant_id.inventory_item_id, int(variant_quantity))
                except Exception as e:
                    if e.code == 429:
                        time.sleep(3)
                        shopify.InventoryLevel.set(shopify_location_id.shopify_location_id, shopify_variant_id.inventory_item_id, int(variant_quantity))
                    else:
                        raise AccessError(_("Error while trying to export stock for Shopify Product Variant: {}, ERROR: {}.".format(shopify_variant_id.name, e)))

    def cron_auto_export_stock(self, mk_instance_id):
        mk_instance_id = self.env['mk.instance'].browse(mk_instance_id)
        self.update_stock_in_shopify_ts(mk_instance_id)
        return True

    def update_stock_in_shopify_ts(self, mk_instance_ids):
        if not isinstance(mk_instance_ids, list):
            mk_instance_ids = [mk_instance_ids]
        for mk_instance_id in mk_instance_ids:
            shopify_template_ids = []
            mk_log_id = self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, operation_type='export')
            mk_log_line_dict = {'error': [], 'success': []}
            mk_instance_id.connection_to_shopify()
            result = self.get_mk_listing_item(mk_instance_id)
            if result:
                shopify_template_ids = self.browse(result)
            # if not shopify_template_ids:
            #     shopify_template_ids = self.search([('mk_instance_id', '=', mk_instance_id.id), ('is_listed', '=', True)])

            location_ids = self.env['shopify.location.ts'].search([('mk_instance_id', '=', mk_instance_id.id)])
            if not location_ids:
                log_message = "No location found for Shopify Account {} at the time of Import stock!".format(
                    mk_instance_id.name)
                mk_log_line_dict['error'].append({'log_message': 'UPDATE STOCK: {}'.format(log_message)})
                return False
            for shopify_location_id in location_ids:
                warehouse_id = shopify_location_id.warehouse_id or False
                if not warehouse_id:
                    log_message = "Warehouse is not set for Shopify Location {}".format(shopify_location_id.name)
                    mk_log_line_dict['error'].append({'log_message': 'UPDATE STOCK: {}'.format(log_message)})
                    continue
                for shopify_template_id in shopify_template_ids:
                    # Commented below code to reduce 1 API call.
                    # try:
                    #     shopify_product = shopify.Product().find(shopify_template_id.mk_id)
                    # except Exception:
                    #     log_message = "Shopify Template {} not found in Shopify while trying to Export Stock.".format(shopify_template_id.mk_id)
                    #     mk_log_line_dict['error'].append({'log_message': 'UPDATE STOCK: {}'.format(log_message)})
                    #     continue
                    # shopify_product.id = shopify_template_id.mk_id
                    for shopify_variant_id in shopify_template_id.listing_item_ids:
                        if shopify_variant_id.product_id.type == 'product' and not shopify_variant_id.inventory_item_id:
                            log_message = "Inventory Item ID not found for Product Variant: {} while export stock.".format(shopify_variant_id.name)
                            mk_log_line_dict['error'].append({'log_message': 'UPDATE STOCK: {}'.format(log_message)})
                            continue
                        variant_quantity = shopify_variant_id.product_id.get_product_stock(shopify_variant_id.export_qty_type, shopify_variant_id.export_qty_value, warehouse_id,
                                                                                           mk_instance_id.stock_field_id.name)
                        try:
                            shopify.InventoryLevel.set(shopify_location_id.shopify_location_id, shopify_variant_id.inventory_item_id, int(variant_quantity))
                        except Exception as e:
                            if e.code == 429:
                                time.sleep(3)
                                shopify.InventoryLevel.set(shopify_location_id.shopify_location_id, shopify_variant_id.inventory_item_id, int(variant_quantity))
                            else:
                                log_message = "Error while trying to export stock for Shopify Product Variant: {}, ERROR: {}.".format(shopify_variant_id.name, e)
                                mk_log_line_dict['error'].append({'log_message': 'UPDATE STOCK: {}'.format(log_message)})
                                continue
                        log_message = "Successfully Updated {} Listing Stock in Shopify.".format(shopify_variant_id.name)
                        mk_log_line_dict['success'].append({'log_message': 'UPDATE STOCK: {}'.format(log_message)})
            mk_instance_id.last_stock_update_date = fields.Datetime.now()
            self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict=mk_log_line_dict)
            if not mk_log_id.log_line_ids:
                mk_log_id.unlink()
        return True

    def cron_auto_import_stock(self, mk_instance_id):
        mk_instance_id = self.env['mk.instance'].browse(mk_instance_id)
        self.shopify_import_stock(mk_instance_id)
        return True

    def shopify_open_listing_in_marketplace(self):
        marketplace_url = self.mk_instance_id.shop_url + '/admin/products/' + self.mk_id
        return marketplace_url
