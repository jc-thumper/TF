from odoo import models, fields


class ShopifyPaymentGateway(models.Model):
    _name = 'shopify.payment.gateway.ts'
    _description = "Shopify Payment Gateway"

    name = fields.Char("Name", required=1)
    code = fields.Char("Code", copy=False)
    mk_instance_id = fields.Many2one('mk.instance', "Instance", copy=False, ondelete='cascade')
