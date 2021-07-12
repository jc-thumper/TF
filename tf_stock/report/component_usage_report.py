from odoo import api, fields, models, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    vendor_id = fields.Many2one(
        comodel_name='res.partner',
        string='Main Vendor',
        compute='_compute_main_vendor',
        store=True,
        help="Technical field for getting first vendor set on product"
    )

    @api.depends('seller_ids', 'seller_ids.sequence')
    def _compute_main_vendor(self):
        for record in self:
            if not record.seller_ids:
                record.vendor_id = False
            else:
                record.vendor_id = record.seller_ids[0].name


class ComponentUsageReport(models.Model):
    _inherit = 'stock.move.line'

    categ_id = fields.Many2one('product.category', 'Product Category', related='product_id.categ_id', store=True)
    vendor_id = fields.Many2one('res.partner', 'Product Vendor', search='_search_vendor', store=False)
    work_center_id = fields.Many2one('mrp.workcenter', 'Work Center', related='workorder_id.workcenter_id')

    def _search_vendor(self, operator, value):
        vendors = self.env["res.partner"].browse()
        if operator == "=" and isinstance(value, int):
            vendors = self.env['res.partner'].search([('id', operator, value)], limit=1)
        else:
            vendors = self.env['res.partner'].search([('name', operator, value)])

        if not vendors:
            return []

        products = self.env['product.product'].search([('vendor_id', 'in', vendors.ids)])
        sml = self.env['stock.move.line'].search([('product_id', 'in', products.ids)])

        return [('id', 'in', sml.ids)]
