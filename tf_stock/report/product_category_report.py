from odoo import api, fields, models, _


class ProductInherit(models.Model):
    _inherit = 'product.product'

    reserved_quantity = fields.Float('Reserved Quantity', compute='_compute_reserved_quantity')

    @api.depends('stock_quant_ids', 'stock_quant_ids.reserved_quantity')
    def _compute_reserved_quantity(self):
        for record in self:
            record.reserved_quantity = sum(self.env['stock.quant'].search([('product_id.type', '=', 'product'),
                                                                           ('product_id', '=', record.id),
                                                                           ('location_id.usage', '=', 'internal')]).mapped('reserved_quantity'))
