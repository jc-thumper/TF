import base64
import requests
from odoo import models, fields


class ShopifyListingImage(models.Model):
    _name = "shopify.product.image.ts"
    _description = 'Shopify Product Image'

    def convert_url_to_binary(self):
        for image in self:
            if image.url:
                image.url_image_id = base64.b64encode(requests.get(self.url).content)

    name = fields.Char("Name")
    image_position = fields.Integer('Image Position')
    mk_listing_id = fields.Many2one('mk.listing', string='Listing', ondelete='cascade')
    shopify_variant_ids = fields.Many2many('mk.listing.item', 'shopify_product_variant_image_rel',
                                           'shopify_product_image_id', 'shopify_variant_id', 'Product Variants')
    mk_instance_id = fields.Many2one("mk.instance", string="Marketplace Instance", related="mk_listing_id.mk_instance_id", ondelete='cascade')
    width = fields.Integer('Image Width')
    height = fields.Integer('Image Height')
    url = fields.Char(size=600, string='Image URL')
    image = fields.Binary("Image")
    url_image_id = fields.Binary("Product Image", compute="convert_url_to_binary", store=False)
    shopify_image_id = fields.Char("Shopify Image Id")
