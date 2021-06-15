from odoo import api, fields, models, _


class ComponentUsageReport(models.Model):
    _inherit = 'stock.move.line'

    categ_id = fields.Many2one('product.category', 'Product Category', related='product_id.categ_id', store=True)
    # seller_ids = fields.Many2one('product.product', 'Product Vendor', related='product_id.seller_ids')
    work_center_id = fields.Many2one('mrp.workcenter', 'Work Center', related='workorder_id.workcenter_id')
