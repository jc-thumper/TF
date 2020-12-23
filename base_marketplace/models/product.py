import hashlib
from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def prepare_vals_for_create_listing(self, instance):
        self.ensure_one()
        vals = {
            'name': self.name,
            'mk_instance_id': instance.id,
            'product_tmpl_id': self.id,
            'description': self.description_sale,
            'product_category_id': self.categ_id.id
        }
        if hasattr(self, '%s_prepare_vals_for_create_listing' % instance.marketplace):
            vals.update(getattr(self, '%s_prepare_vals_for_create_listing' % instance.marketplace)(instance))
        return vals

    def prepare_vals_for_update_listing(self, instance):
        self.ensure_one()
        vals = {
            'product_category_id': self.categ_id.id,
        }
        if hasattr(self, '%s_prepare_vals_for_update_listing' % instance.marketplace):
            vals.update(getattr(self, '%s_prepare_vals_for_update_listing' % instance.marketplace)(instance))
        return vals

    def create_or_update_listing_image(self, listing_id):
        if not self.image_1920:
            return True
        listing_image_obj = self.env['mk.listing.image']
        image_hex = hashlib.md5(self.image_1920).hexdigest()
        listing_image_id = listing_image_obj.search([('image_hex', '=', image_hex), ('mk_listing_id', '=', listing_id.id)], limit=1)
        if listing_image_id:
            return True
        listing_image_obj.create({'name': listing_id.name, 'image': self.image_1920, 'mk_listing_id': listing_id.id, })
        return True

    def create_or_update_listing(self, instance):
        self.ensure_one()
        listing_obj = self.env['mk.listing']
        listing_id = listing_obj.search([('mk_instance_id', '=', instance.id), ('product_tmpl_id', '=', self.id)])
        if not listing_id:
            vals = self.prepare_vals_for_create_listing(instance)
            listing_id = listing_obj.create(vals)
        else:
            vals = self.prepare_vals_for_update_listing(instance)
            listing_id.write(vals)
        # self.create_or_update_listing_image(listing_id)
        sequence = 1
        for product_variant_id in self.product_variant_ids:
            product_variant_id.create_or_update_listing_item(instance, sequence, listing_id)
            sequence += 1
        return listing_id

    mk_listing_ids = fields.One2many('mk.listing', 'product_tmpl_id', string="Listing")


class ProductProduct(models.Model):
    _inherit = "product.product"

    mk_listing_item_ids = fields.One2many('mk.listing.item', 'product_id', string="Listing Items")

    def prepare_vals_for_create_listing_item(self, instance, sequence, listing_id):
        self.ensure_one()
        vals = {
            'name': self.name,
            'sequence': sequence,
            'mk_instance_id': instance.id,
            'product_id': self.id,
            'default_code': self.default_code,
            'mk_listing_id': listing_id.id
        }
        if hasattr(self, '%s_prepare_vals_for_create_listing_item' % instance.marketplace):
            vals.update(getattr(self, '%s_prepare_vals_for_create_listing_item' % instance.marketplace)(instance))
        return vals

    def prepare_vals_for_update_listing_item(self, instance, sequence, listing_id):
        self.ensure_one()
        vals = {
            'sequence': sequence,
            'default_code': self.default_code,
        }
        if hasattr(self, '%s_prepare_vals_for_update_listing_item' % instance.marketplace):
            vals.update(getattr(self, '%s_prepare_vals_for_update_listing_item' % instance.marketplace)(instance))
        return vals

    def create_or_update_listing_image(self, listing_item_id):
        if not self.image_1920:
            return True
        listing_image_obj = self.env['mk.listing.image']
        image_hex = hashlib.md5(self.image_1920).hexdigest()
        listing_image_id = listing_image_obj.search([('image_hex', '=', image_hex), ('mk_listing_item_ids', 'in', listing_item_id.ids)], limit=1)
        if listing_image_id:
            return True
        listing_image_obj.create(
            {'name': listing_item_id.name, 'image': self.image_1920, 'mk_listing_id': listing_item_id.mk_listing_id.id, 'mk_listing_item_ids': [(6, 0, listing_item_id.ids)]})
        return True

    def create_or_update_listing_item(self, instance, sequence, listing_id):
        self.ensure_one()
        listing_item_obj = self.env['mk.listing.item']
        listing_item_id = listing_item_obj.search([('mk_instance_id', '=', instance.id), ('product_id', '=', self.id)])
        if not listing_item_id:
            vals = self.prepare_vals_for_create_listing_item(instance, sequence, listing_id)
            listing_item_id = listing_item_obj.create(vals)
            listing_item_id.create_or_update_pricelist_item(float(self.lst_price))
        else:
            vals = self.prepare_vals_for_update_listing_item(instance, sequence, listing_id)
            listing_item_id.write(vals)
            pricelist_item_id = self.env['product.pricelist.item'].search([('pricelist_id', '=', instance.pricelist_id.id), ('product_id', '=', listing_item_id.product_id.id)],
                                                                          limit=1)
            if not pricelist_item_id:
                listing_item_id.create_or_update_pricelist_item(float(self.lst_price))
        self.create_or_update_listing_image(listing_item_id)
        return listing_id

    def get_product_stock(self, export_qty_type, export_qty_value, warehouse_id, stock_type):
        product_id = self.with_context(warehouse=warehouse_id.id)
        stock = getattr(product_id, stock_type)
        if stock > 0:
            if export_qty_type == 'percentage':
                quantity = (stock * export_qty_value) / 100
                if quantity >= stock:
                    return stock
                else:
                    return quantity
            elif export_qty_type == 'fix':
                if export_qty_value >= stock:
                    return stock
                else:
                    return export_qty_value
        return stock


class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    def create_or_update_ptal(self, attribute_dict, product_tmpl_id, attribute_line_vals):
        for name, value in attribute_dict.items():
            ptal_id = self.env['product.template.attribute.line'].search([('product_tmpl_id', '=', product_tmpl_id.id), ('attribute_id.name', '=ilike', name)])
            if not ptal_id:
                product_tmpl_id.write({'attribute_line_ids': attribute_line_vals})
                ptal_id = self.search([('product_tmpl_id', '=', product_tmpl_id.id), ('attribute_id.name', '=ilike', name)])
            attribute_value_id = self.env['product.attribute.value'].search([('name', '=ilike', value), ('attribute_id', '=', ptal_id.attribute_id.id)], limit=1)
            if not attribute_value_id:
                attribute_value_id = self.env['product.attribute.value'].create({'name': value, 'attribute_id': ptal_id.attribute_id.id})
            if attribute_value_id not in ptal_id.value_ids:
                ptal_id.write({'value_ids': [(4, attribute_value_id.id, False)]})
        return True
