from odoo import fields, models, _


class StockInventory(models.Model):
    _inherit = "stock.inventory"

    is_shopify_adjustment = fields.Boolean("Is Shopify Adjustment")
    updated_in_shopify = fields.Boolean("Updated In Shopify", default=False)
