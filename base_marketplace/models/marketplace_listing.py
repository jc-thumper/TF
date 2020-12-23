import json
from lxml import etree
from datetime import timedelta
from odoo.osv import expression
from odoo import models, fields, api, _


class MkListing(models.Model):
    _name = "mk.listing"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Marketplace Listing'

    def _listing_item_count(self):
        for listing in self:
            listing.item_count = len(listing.listing_item_ids)

    name = fields.Char('Name', required=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', ondelete='cascade')
    product_category_id = fields.Many2one("product.category", "Product Category")
    listing_item_ids = fields.One2many("mk.listing.item", "mk_listing_id", "Listing Items")
    item_count = fields.Integer("Items", compute='_listing_item_count')
    mk_id = fields.Char("Marketplace Identification", copy=False)
    mk_instance_id = fields.Many2one('mk.instance', "Instance", ondelete='cascade')
    mk_instance_image = fields.Binary(related="mk_instance_id.image_small", string="Marketplace Image", help="Technical field to get the instance image for display purpose.",
                                      store=False)
    marketplace = fields.Selection(related="mk_instance_id.marketplace", string='Marketplace')
    listing_create_date = fields.Datetime("Creation Date", readonly=True, index=True)
    listing_update_date = fields.Datetime("Updated On", readonly=True)
    listing_publish_date = fields.Datetime("Published On", readonly=True)
    description = fields.Html('Description', sanitize_attributes=False)
    is_listed = fields.Boolean("Listed?", copy=False, track_visibility='onchange')
    is_published = fields.Boolean("Published", copy=False, track_visibility='onchange')
    image_ids = fields.One2many('mk.listing.image', 'mk_listing_id', 'Images')
    number_of_variants_in_mk = fields.Integer("Number of Variants in Marketplace.")

    def get_fields_for_hide(self):
        marketplace_list = self.env['mk.instance'].get_all_marketplace()
        field_dict = {}
        for marketplace in marketplace_list:
            if hasattr(self, '%s_hide_fields' % marketplace):
                field_list = getattr(self, '%s_hide_fields' % marketplace)()
                field_dict.update({marketplace: field_list})
        return field_dict

    def get_page_for_hide(self):
        marketplace_list = self.env['mk.instance'].get_all_marketplace()
        page_dict = {}
        for marketplace in marketplace_list:
            if hasattr(self, '%s_hide_page' % marketplace):
                page_list = getattr(self, '%s_hide_page' % marketplace)()
                page_dict.update({marketplace: page_list})
        return page_dict

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        ret_val = super(MkListing, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        need_to_hide_field_dict = self.get_fields_for_hide()
        doc = etree.XML(ret_val['arch'])
        if view_type == 'form':
            # For hide page
            need_to_hide_page_list = self.get_page_for_hide()
            for marketplace, instance_field_list in need_to_hide_page_list.items():
                for page in instance_field_list:
                    for node in doc.xpath("//page[@name='%s']" % page):
                        existing_domain, new_domain = [], []
                        if not node.get("modifiers"):
                            node.set("modifiers", json.dumps({'invisible': [('marketplace', '=', marketplace)]}))
                            continue
                        modifiers = json.loads(node.get("modifiers"))
                        if 'invisible' in modifiers and isinstance(modifiers['invisible'], list):
                            if not existing_domain:
                                existing_domain = modifiers['invisible']
                            if not new_domain:
                                new_domain = [('marketplace', '=', marketplace)]
                            else:
                                new_domain = expression.OR([new_domain, [('marketplace', '=', marketplace)]])
                        else:
                            modifiers['invisible'] = [('marketplace', '=', marketplace)]
                        node.set("modifiers", json.dumps(modifiers))
                        if existing_domain and new_domain:
                            node.set("modifiers", json.dumps({'invisible': expression.OR([existing_domain, new_domain])}))

        for field in ret_val['fields']:
            for node in doc.xpath("//field[@name='%s']" % field):
                existing_domain, new_domain = [], []
                for marketplace, field_list in need_to_hide_field_dict.items():
                    if field in field_list:
                        modifiers = json.loads(node.get("modifiers"))
                        if 'invisible' in modifiers and isinstance(modifiers['invisible'], list):
                            if not existing_domain:
                                existing_domain = modifiers['invisible']
                            if not new_domain:
                                new_domain = [('marketplace', '=', marketplace)]
                            else:
                                new_domain = expression.OR([new_domain, [('marketplace', '=', marketplace)]])
                        else:
                            modifiers['invisible'] = [('marketplace', '=', marketplace)]
                        node.set("modifiers", json.dumps(modifiers))
                if existing_domain and new_domain:
                    force_modifiers = {}
                    force_modifiers['invisible'] = expression.OR([existing_domain, new_domain])
                    node.set("modifiers", json.dumps(force_modifiers))
        ret_val['arch'] = etree.tostring(doc, encoding='unicode')
        return ret_val

    def _marketplace_convert_weight(self, weight, weight_name):
        mk_uom_id = False
        if weight_name == 'lb':
            mk_uom_id = self.env.ref('uom.product_uom_lb')
        elif weight_name == 'kg':
            mk_uom_id = self.env.ref('uom.product_uom_kgm')
        elif weight_name == 'oz':
            mk_uom_id = self.env.ref('uom.product_uom_oz')
        elif weight_name == 'g':
            mk_uom_id = self.env.ref('uom.product_uom_gram')
        elif weight_name == 't':
            mk_uom_id = self.env.ref('uom.product_uom_ton')
        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        if mk_uom_id:
            return mk_uom_id._compute_quantity(weight, weight_uom_id, round=False)
        return False

    def get_odoo_product_variant_and_listing_item(self, mk_instance_id, variant_id, variant_barcode, variant_sku):
        odoo_product_obj, mk_listing_item_obj, odoo_product_id = self.env['product.product'], self.env['mk.listing.item'], False
        listing_item_id = mk_listing_item_obj.search([('mk_id', '=', variant_id), ('mk_instance_id', '=', mk_instance_id.id)], limit=1)
        if mk_instance_id.sync_product_with == 'barcode' and variant_barcode:
            if not listing_item_id:
                listing_item_id = mk_listing_item_obj.search([('product_id.barcode', '=', variant_barcode), ('mk_id', '=', variant_id), ('mk_instance_id', '=', mk_instance_id.id)],
                                                             limit=1)
            if not listing_item_id:
                odoo_product_id = odoo_product_obj.search([('barcode', '=', variant_barcode)], limit=1)

        if mk_instance_id.sync_product_with == 'sku' and variant_sku:
            if not listing_item_id:
                listing_item_id = mk_listing_item_obj.search([('default_code', '=', variant_sku), ('mk_id', '=', variant_id), ('mk_instance_id', '=', mk_instance_id.id)], limit=1)
            if not listing_item_id:
                listing_item_id = mk_listing_item_obj.search(
                    [('product_id.default_code', '=', variant_sku), ('mk_id', '=', variant_id), ('mk_instance_id', '=', mk_instance_id.id)], limit=1)
            if not listing_item_id:
                odoo_product_id = odoo_product_obj.search([('default_code', '=', variant_sku)], limit=1)

        if mk_instance_id.sync_product_with == 'barcode_or_sku':
            if variant_sku and not listing_item_id:
                listing_item_id = mk_listing_item_obj.search([('default_code', '=', variant_sku), ('mk_id', '=', variant_id), ('mk_instance_id', '=', mk_instance_id.id)], limit=1)
            if variant_barcode and not listing_item_id:
                listing_item_id = mk_listing_item_obj.search([('product_id.barcode', '=', variant_sku), ('mk_id', '=', variant_id), ('mk_instance_id', '=', mk_instance_id.id)],
                                                             limit=1)
            if not listing_item_id and variant_sku:
                odoo_product_id = odoo_product_obj.search([('default_code', '=', variant_sku)], limit=1)
            if not odoo_product_id and not listing_item_id and variant_barcode:
                odoo_product_id = odoo_product_obj.search([('barcode', '=', variant_barcode)], limit=1)
        return odoo_product_id, listing_item_id

    def check_for_duplicate_sku_or_barcode_in_marketplace_product(self, sync_product_with, listing_item_validation_dict):
        mk_sku_list = []
        mk_barcode_list = []
        for mk_variant in listing_item_validation_dict.get('variants'):
            if not mk_variant.get('sku', False) and not mk_variant.get('barcode', False):
                return False, "IMPORT LISTING: SKU and Barcode not set in Marketplace for Product: {} and Marketplace Listing ID: {}".format(
                    listing_item_validation_dict.get('name'), listing_item_validation_dict.get('id'))
            if sync_product_with == 'sku' and not mk_variant.get('sku', False):
                return False, "IMPORT LISTING: SKU not set in Marketplace for Product: {} and Marketplace Listing ID: {}".format(listing_item_validation_dict.get('name'),
                                                                                                                                 listing_item_validation_dict.get('id'))
            elif sync_product_with == 'barcode' and not mk_variant.get('barcode', False):
                return False, "IMPORT LISTING: Barcode not set in Marketplace for Product: {} and Marketplace Listing ID: {}".format(listing_item_validation_dict.get('name'),
                                                                                                                                     listing_item_validation_dict.get('id'))
            mk_variant.get('sku', False) and mk_sku_list.append(mk_variant.get('sku', False))
            mk_variant.get('barcode', False) and mk_barcode_list.append(mk_variant.get('barcode', False))
        count_unique_sku = len(set(mk_sku_list))
        count_unique_barcode = len(set(mk_barcode_list))

        # Always need to check for unique barcode because Odoo isn't allowing to create product with same barcode.
        if mk_barcode_list and not len(mk_barcode_list) == count_unique_barcode:
            return False, "IMPORT LISTING: Duplicate Barcode found in Marketplace for Product {} and MK ID: {}".format(listing_item_validation_dict.get('name'),
                                                                                                                       listing_item_validation_dict.get('id'))

        # checking for duplicate SKU or Barcode from marketplace product.
        if sync_product_with == 'sku' and not len(mk_sku_list) == count_unique_sku:
            return False, "IMPORT LISTING: Duplicate SKU found in Marketplace for Product {} and MK ID: {}".format(listing_item_validation_dict.get('name'),
                                                                                                                   listing_item_validation_dict.get('id'))
        elif sync_product_with == 'barcode' and not len(mk_barcode_list) == count_unique_barcode:
            return False, "IMPORT LISTING: Duplicate Barcode found in Marketplace for Product {} and MK ID: {}".format(listing_item_validation_dict.get('name'),
                                                                                                                       listing_item_validation_dict.get('id'))
        elif sync_product_with == 'barcode_or_sku':
            if (mk_barcode_list and len(mk_barcode_list) == count_unique_barcode) or (mk_sku_list and len(mk_sku_list) == count_unique_sku):
                return True, ""
            if not len(mk_sku_list) == count_unique_sku:
                return False, "IMPORT LISTING: Duplicate SKU found in Marketplace for Product {} and MK ID: {}".format(listing_item_validation_dict.get('name'),
                                                                                                                       listing_item_validation_dict.get('id'))
            if not len(mk_barcode_list) == count_unique_barcode:
                return False, "IMPORT LISTING: Duplicate Barcode found in Marketplace for Product {} and MK ID: {}".format(listing_item_validation_dict.get('name'),
                                                                                                                           listing_item_validation_dict.get('id'))
        return True, ""

    def check_validation_for_import_product(self, sync_product_with, listing_item_validation_dict, product_tmpl_id, existing_odoo_product, existing_mk_product):
        mk_sku_list = []
        mk_barcode_list = []
        for mk_variant in listing_item_validation_dict.get('variants'):
            variant_id = mk_variant.get('id')
            mk_variant.get('sku', False) and mk_sku_list.append(mk_variant.get('sku', False))
            mk_variant.get('barcode', False) and mk_barcode_list.append(mk_variant.get('barcode', False))
            barcode = mk_variant.get('barcode', False)
            listing_item_id = existing_mk_product.get(variant_id, False)
            odoo_product_id = existing_odoo_product.get(variant_id, False)

            # Looking for Odoo product having the same barcode to avoid duplication of Odoo product.
            if barcode:
                if not odoo_product_id and self.env['product.product'].search([('barcode', '=', barcode)]):
                    return False, "IMPORT LISTING: Duplicate Barcode ({}) found in Odoo for Product {} and MK ID: {}".format(barcode, listing_item_validation_dict.get('name'),
                                                                                                                             listing_item_validation_dict.get('id'))
                elif listing_item_id and self.env['product.product'].search([('barcode', '=', barcode), ('id', '!=', listing_item_id.product_id.id)]):
                    return False, "IMPORT LISTING: Duplicate Barcode ({}) found in Odoo for Product {} and MK ID: {}".format(barcode, listing_item_validation_dict.get('name'),
                                                                                                                             listing_item_validation_dict.get('id'))

        # comparing existing Odoo product's variants with the marketplace product's variants only if both having same variation count.
        if product_tmpl_id:
            count_mk_no_of_variants = len(listing_item_validation_dict.get('variants'))
            if count_mk_no_of_variants > 1 and product_tmpl_id.product_variant_count > 1:
                if count_mk_no_of_variants == product_tmpl_id.product_variant_count:
                    odoo_products_sku = set([x.default_code if x.default_code else False for x in product_tmpl_id.product_variant_ids])
                    odoo_products_barcode = set([x.barcode if x.barcode else False for x in product_tmpl_id.product_variant_ids])
                    if sync_product_with == 'sku':
                        for mk_sku in mk_sku_list:
                            if mk_sku not in odoo_products_sku:
                                return False, "IMPORT LISTING: No SKU found in Odoo Product: {} for Marketplace Product : {} and SKU: {}".format(odoo_product_id.name,
                                                                                                                                                 listing_item_validation_dict.get(
                                                                                                                                                     'name'), mk_sku)
                    elif sync_product_with == 'barcode':
                        for mk_barcode in mk_barcode_list:
                            if mk_barcode not in odoo_products_barcode:
                                return False, "IMPORT LISTING: No Barcode found in Odoo Product: {} for Marketplace Product : {} and Barcode: {}".format(odoo_product_id.name,
                                                                                                                                                         listing_item_validation_dict.get(
                                                                                                                                                             'name'), mk_barcode)
        return True, ""

    def _find_odoo_product_from_marketplace_attribute(self, mk_attribute_dict, product_tmpl_id):
        domain = [('product_tmpl_id', '=', product_tmpl_id.id)]
        for name, value in mk_attribute_dict.items():
            attribute_id = self.env['product.attribute'].search([('name', '=ilike', name)], limit=1)
            attribute_value_id = self.env['product.attribute.value'].search([('attribute_id', '=', attribute_id.id), ('name', '=ilike', value)], limit=1)
            if attribute_value_id:
                ptav_id = self.env['product.template.attribute.value'].search([
                    ('product_attribute_value_id', '=', attribute_value_id.id), ('attribute_id', '=', attribute_id.id), ('product_tmpl_id', '=', product_tmpl_id.id)], limit=1)
                if ptav_id:
                    domain.append(('product_template_attribute_value_ids', '=', ptav_id.id))
        return self.env['product.product'].search(domain)

    def open_listing_in_marketplace(self):
        self.ensure_one()
        if hasattr(self, '%s_open_listing_in_marketplace' % self.marketplace):
            url = getattr(self, '%s_open_listing_in_marketplace' % self.marketplace)()
            if url:
                client_action = {
                    'type': 'ir.actions.act_url',
                    'name': "Marketplace URL",
                    'target': 'new',
                    'url': url,
                }
                return client_action

    def marketplace_published(self):
        if hasattr(self, '%s_published' % self.marketplace):
            getattr(self, '%s_published' % self.marketplace)()
        return True

    def action_open_update_listing_view(self):
        active_model = self._context.get('active_model')
        active_ids = self._context.get('active_ids')
        if active_model == 'mk.listing' and active_ids:
            listing = self.env[active_model].browse(active_ids)
            listing_instance = listing.mapped('mk_instance_id')
            # making sure we only open marketplace wise view only if selected listing belongs to single instance.
            if len(listing_instance) == 1:
                if hasattr(self, '%s_open_update_listing_view' % listing_instance.marketplace):
                    return getattr(self, '%s_open_update_listing_view' % listing_instance.marketplace)()
        action = self.env.ref('base_marketplace.action_listing_update_to_marketplace').read()[0]
        context = self._context.copy()
        action['context'] = context
        return action

    def get_mk_listing_item(self, mk_instance_id):
        query = """
                select mkl.id
                from stock_move sm
                         join mk_listing_item mkli on sm.product_id = mkli.product_id
                         join mk_listing mkl on mkl.id = mkli.mk_listing_id and mkl.is_listed = true and mkl.mk_instance_id = {}
                where DATE(sm.write_date) >= '{}'
                  and state in ('done', 'cancel')
        """.format(mk_instance_id.id, mk_instance_id.last_stock_update_date or fields.Datetime.now() - timedelta(30))
        self._cr.execute(query)
        result = [int(i[0]) for i in self._cr.fetchall()]
        return list(set(result))

    def remove_extra_listing_item(self, mk_id_list):
        if mk_id_list:
            mk_log_id = self.env.context.get('mk_log_id', False)
            queue_line_id = self.env.context.get('queue_line_id', False)
            odoo_variant_id_list = [item_id.mk_id for item_id in self.listing_item_ids]
            need_to_remove_id_set = set(mk_id_list) ^ set(odoo_variant_id_list)
            if need_to_remove_id_set:
                need_to_remove_id_list = list(need_to_remove_id_set)
                self.env['mk.listing.item'].search([('mk_id', 'in', need_to_remove_id_list)]).unlink()
                self.env['mk.log'].create_update_log(mk_instance_id=self.mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict={'success': [
                    {'log_message': 'IMPORT LISTING: {} listing item deleted.'.format(need_to_remove_id_list), 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
        return True
