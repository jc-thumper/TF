from odoo import models, fields

CONTINUE_SELLING = [('continue', 'Allow'), ('deny', 'Deny'), ('parent_product', 'Same as Product Template')]
INVENTORY_MANAGEMENT = [('shopify', 'Track Quantity'), ('dont_track', 'Dont track Inventory')]


class MkListingItem(models.Model):
    _inherit = "mk.listing.item"

    inventory_item_id = fields.Char('Inventory Item ID')
    shopify_image_id = fields.Char("Shopify Image ID")
    inventory_management = fields.Selection(INVENTORY_MANAGEMENT, default='shopify')
    continue_selling = fields.Selection(CONTINUE_SELLING, default='parent_product', help='If true then Customer can place order while product is out of stock.')
