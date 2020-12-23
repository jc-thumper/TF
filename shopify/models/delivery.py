from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    shopify_code = fields.Char(string='Shopify Carrier Code')
