from odoo import api, fields, models, _


class ProductInherit(models.Model):
    _inherit = 'product.product'

    reserved_quantity = fields.Float('Reserved Quantity', compute='_compute_reserved_quantity')

    @api.depends('stock_quant_ids', 'stock_quant_ids.reserved_quantity')
    def _compute_reserved_quantity(self):
        reserved_quantity_dict = self.env['stock.quant'].read_group(domain=[('product_id.type', '=', 'product'),
                                                                            ('location_id.usage', '=', 'internal')],
                                                                    fields=['product_id', 'total_reserved_quantity:sum(reserved_quantity)'],
                                                                    groupby=['product_id'])
        mapped_data = dict([(m['product_id'][0], m['total_reserved_quantity']) for m in reserved_quantity_dict])
        for record in self:
            record.reserved_quantity = mapped_data.get(record.id, 0)
