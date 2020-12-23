from odoo import models, fields

STATUS_SELECTION = [('shipped', 'Shipped'),
                    ('partial', 'Partial'),
                    ('unshipped', 'Un-shipped'),
                    ('any', 'Any')]


class ShopifyOrderStatus(models.Model):
    _name = 'shopify.order.status'
    _description = "Shopify Order Status"

    name = fields.Char("Name", required=1)
    status = fields.Selection(STATUS_SELECTION, "Fulfillment Status")
