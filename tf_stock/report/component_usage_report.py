from odoo import api, fields, models, _

import time
from datetime import timedelta


class ProductProduct(models.Model):
    _inherit = 'product.product'

    vendor_id = fields.Many2one('res.partner', string='Main Vendor', store=True, compute='_compute_main_vendor')

    @api.depends('seller_ids', 'seller_ids.sequence')
    def _compute_main_vendor(self):
        for record in self:
            record.vendor_id = record.seller_ids[:1].name.id


class ComponentUsageReport(models.Model):
    _inherit = 'stock.move.line'

    categ_id = fields.Many2one('product.category', 'Product Category', related='product_id.categ_id', store=True)
    vendor_id = fields.Many2one('product.product', 'Product Vendor', search='_search_vendor', store=False)
    work_center_id = fields.Many2one('mrp.workcenter', 'Work Center', related='workorder_id.workcenter_id')

    def _search_vendor(self, operator, value):
        if operator == 'ilike':
            vendors_ids = self.env['res.partner'].search([('name', 'ilike', value)]).ids
            products_ids = self.env['product.product'].search([('vendor_id', 'in', vendors_ids)]).ids
            sml_ids = self.env['stock.move.line'].search([('product_id', 'in', products_ids)]).ids

        return [('id', 'in', sml_ids)]
