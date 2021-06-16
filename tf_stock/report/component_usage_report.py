from odoo import api, fields, models, _


class ComponentUsageReport(models.Model):
    _inherit = 'stock.move.line'

    categ_id = fields.Many2one('product.category', 'Product Category', related='product_id.categ_id', store=True)
    seller_id = fields.Many2one('product.product', 'Product Vendor', compute='_compute_seller_id', search='_search_seller')
    work_center_id = fields.Many2one('mrp.workcenter', 'Work Center', related='workorder_id.workcenter_id')

    def _compute_seller_id(self):
        for record in self:
            record.seller_id = record.seller_ids[:1].id

    def _search_seller(self, operator, value):
        if operator == 'ilike':
            smls = self.env['stock.move.line'].search([])
            smls_ids = smls.filtered(lambda sml, key=value: sml.product_id.seller_ids[:1].display_name
                                     and key.lower() in sml.product_id.seller_ids[:1].display_name.lower()).ids
        return [('id', 'in', smls_ids)]
