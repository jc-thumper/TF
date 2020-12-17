# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def write(self, vals):
        if not self.env.context.get("from_product"):
            product_type = vals.get('type', self.type)
            uom_id = vals.get('uom_id', self.uom_id.id)
            uom_po_id = vals.get('uom_po_id', self.uom_po_id.id)
            if vals.get('route_ids'):
                route_ids = vals.get('route_ids')[0][2]
            else:
                route_ids = self.route_ids.ids
            sale_ok = vals.get('sale_ok', self.sale_ok)
            purchase_ok = vals.get('purchase_ok', self.purchase_ok)
            bom_count = vals.get('bom_count') or self.bom_count
            if vals.get('seller_ids'):
                seller_ids = vals.get('seller_ids')[0][2]
            else:
                seller_ids = self.seller_ids.ids
            standard_price = vals.get('standard_price', self.standard_price)
            lst_price = vals.get('lst_price', self.lst_price)
            if product_type in ['consu', 'product']:
                if uom_id != uom_po_id:
                    reordering_rule = self.env['stock.warehouse.orderpoint'].search(
                        [('product_id.product_tmpl_id', '=', self.id), ('qty_multiple', '>', 1)])
                    if not reordering_rule:
                        raise UserError(_('Warning ! \n Must have a Reordering rule with Quantity Multiple > 1.'))
                if not route_ids:
                    raise UserError(_('Warning ! \n Please define a Route for the Product.'))
                else:
                    routes = self.env['stock.location.route'].browse(route_ids).mapped('name')
                    if 'Dropship' in routes:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy when using Dropship.'))
                        if not sale_ok or not purchase_ok:
                            raise UserError(
                                _('Warning ! \n Must be Can be Sold & Can be Purchased when using Dropship.'))
                    if len(routes) > 1:
                        if all(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Cannot have both Buy & Manufacture.'))
                    if bom_count >= 1 and 'Manufacture' not in routes:
                        raise UserError(_('Warning ! \n Route must be Manufacture since a BOM exists.'))

                    if sale_ok:
                        if not any(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Route must be Buy or Manufacture'))
                        if standard_price >= lst_price:
                            raise UserError(_('Warning ! \n Cost must be less than Sales price'))
                    else:
                        if lst_price > 0:
                            raise UserError(_('Warning ! \n Sales Price must be $0.00'))
                    if purchase_ok:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy since it can be purchase.'))
                        if not seller_ids:
                            raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
                    else:
                        if 'Manufacture' not in routes:
                            raise UserError(_('Warning ! \n Route must be Manufacture.'))
        self = self.with_context(from_template=True)
        return super(ProductTemplate, self).write(vals)

    @api.model
    def create(self, vals):
        res = super(ProductTemplate, self).create(vals)
        if not self.env.context.get("from_product"):
            self = self.with_context(from_template=True)
            if res.type in ['consu', 'product']:
                if res.uom_id != res.uom_po_id:
                    reordering_rule = self.env['stock.warehouse.orderpoint'].search(
                        [('product_id', '=', res.id), ('qty_multiple', '>', 1)])
                    if not reordering_rule:
                        raise UserError(_('Warning ! \n Must have a Reordering rule with Quantity Multiple > 1.'))
                if not res.route_ids:
                    raise UserError(_('Warning ! \n Please define a Route for the Product.'))
                else:
                    routes = res.route_ids.mapped('name')
                    if 'Dropship' in routes:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy when using Dropship.'))
                        if not res.sale_ok or not res.purchase_ok:
                            raise UserError(
                                _('Warning ! \n Must be Can be Sold & Can be Purchased when using Dropship.'))
                    if len(res.route_ids) > 1:
                        if all(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Cannot have both Buy & Manufacture.'))
                    if res.bom_count > 1 and 'Manufacture' not in routes:
                        raise UserError(_('Warning ! \n Route must be Manufacture since a BOM exists.'))
                    if res.sale_ok:
                        if not any(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Route must be Buy or Manufacture'))
                        if res.standard_price >= res.list_price:
                            raise UserError(_('Warning ! \n Cost must be less than Sales price'))
                    else:
                        if res.lst_price > 0:
                            raise UserError(_('Warning ! \n Sales Price must be $0.00'))
                    if res.purchase_ok:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy since it can be purchase.'))
                        if not res.seller_ids:
                            raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
                    else:
                        if 'Manufacture' not in routes:
                            raise UserError(_('Warning ! \n Route must be Manufacture since it cant be Purchased.'))
        return res


class Product(models.Model):
    _inherit = "product.product"

    weight = fields.Float('Weight', digits='Stock Weight', default=0.01)

    @api.model
    def create(self, vals):
        self = self.with_context(from_product=True)
        res = super(Product, self).create(vals)
        if not self.env.context.get("from_template"):
            if res.type in ['consu', 'product']:
                if res.uom_id != res.uom_po_id:
                    reordering_rule = self.env['stock.warehouse.orderpoint'].search(
                        [('product_id', '=', res.id), ('qty_multiple', '>', 1)])
                    if not reordering_rule:
                        raise UserError(_('Warning ! \n Must have a Reordering rule with Quantity Multiple > 1.'))
                if not res.route_ids:
                    raise UserError(_('Warning ! \n Please define a Route for the Product.'))
                else:
                    routes = res.route_ids.mapped('name')
                    if 'Dropship' in routes:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy when using Dropship.'))
                        if not res.sale_ok or not res.purchase_ok:
                            raise UserError(
                                _('Warning ! \n Must be Can be Sold & Can be Purchased when using Dropship.'))
                    if len(res.route_ids) > 1:
                        if all(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Cannot have both Buy & Manufacture.'))
                    if res.bom_count > 1 and 'Manufacture' not in routes:
                        raise UserError(_('Warning ! \n Route must be Manufacture since a BOM exists.'))

                    if res.sale_ok:
                        if not any(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Route must be Buy or Manufacture'))
                        if res.standard_price >= res.lst_price:
                            raise UserError(_('Warning ! \n Cost must be less than Sales price'))
                    else:
                        if res.lst_price > 0:
                            raise UserError(_('Warning ! \n Sales Price must be $0.00'))
                    if res.purchase_ok:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy since it can be purchase.'))
                        if not res.seller_ids:
                            raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
                    else:
                        if 'Manufacture' not in routes:
                            raise UserError(_('Warning ! \n Route must be Manufacture.'))
        return res

    def write(self, vals):
        if not self.env.context.get("from_template") and not self.env.context.get("from_product"):
            product_type = vals.get('type', self.type)
            uom_id = vals.get('uom_id', self.uom_id.id)
            uom_po_id = vals.get('uom_po_id', self.uom_po_id.id)
            if vals.get('route_ids'):
                route_ids = vals.get('route_ids')[0][2]
            else:
                route_ids = self.route_ids.ids
            sale_ok = vals.get('sale_ok', self.sale_ok)
            purchase_ok = vals.get('purchase_ok', self.purchase_ok)
            bom_count = vals.get('bom_count') or self.bom_count
            if vals.get('seller_ids'):
                seller_ids = vals.get('seller_ids')[0][2]
            else:
                seller_ids = self.seller_ids.ids
            standard_price = vals.get('standard_price', self.standard_price)
            lst_price = vals.get('lst_price', self.lst_price)

            if product_type in ['consu', 'product']:
                if uom_id != uom_po_id:
                    reordering_rule = self.env['stock.warehouse.orderpoint'].search(
                        [('product_id', '=', self.id), ('qty_multiple', '>', 1)])
                    if not reordering_rule:
                        raise UserError(_('Warning ! \n Must have a Reordering rule with Quantity Multiple > 1.'))
                if not route_ids:
                    raise UserError(_('Warning ! \n Please define a Route for the Product.'))
                else:
                    routes = self.env['stock.location.route'].browse(route_ids).mapped('name')
                    if 'Dropship' in routes:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy when using Dropship.'))
                        if not sale_ok or not purchase_ok:
                            raise UserError(
                                _('Warning ! \n Must be Can be Sold & Can be Purchased when using Dropship.'))
                    if len(routes) > 1:
                        if all(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Cannot have both Buy & Manufacture.'))
                    if bom_count >= 1 and 'Manufacture' not in routes:
                        raise UserError(_('Warning ! \n Route must be Manufacture since a BOM exists.'))
                    if sale_ok:
                        if not any(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Route must be Buy or Manufacture'))
                        if standard_price >= lst_price:
                            raise UserError(_('Warning ! \n Cost must be less than Sales price'))
                    else:
                        if lst_price > 0:
                            raise UserError(_('Warning ! \n Sales Price must be $0.00'))
                    if purchase_ok:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy since it can be purchase.'))
                        if not seller_ids:
                            raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
                    else:
                        if 'Manufacture' not in routes:
                            raise UserError(_('Warning ! \n Route must be Manufacture since it cant be Purchased.'))
        self = self.with_context(from_product=True)
        return super(Product, self).write(vals)


class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    product_name = fields.Char(
        'Vendor Product Name', required=True,
        help="This vendor's product name will be used when printing a request for quotation. Keep empty to use the internal one.")
    product_code = fields.Char(
        'Vendor Product Code', required=True,
        help="This vendor's product code will be used when printing a request for quotation. Keep empty to use the internal one.")

    @api.constrains('min_qty', 'delay')
    def _check_min_qty(self):
        for record in self:
            if record.min_qty < 1:
                raise UserError(_('Vendor Pricelist Quantity must be greater than 0'))
            if record.delay < 1:
                raise UserError(_('Delivery Lead Time must be greater than 0'))


class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    lead_days = fields.Integer(
        'Lead Time', default=0,
        help="Number of days after the orderpoint is triggered to receive the products or to order to the vendor")


class MrpBom(models.Model):
    """ Defines bills of material for a product or a product template """
    _inherit = 'mrp.bom'
    consumption = fields.Selection([
        ('strict', 'Strict'),
        ('flexible', 'Flexible')],
        help="Defines if you can consume more or less components than the quantity defined on the BoM.",
        default='flexible',
        string='Consumption'
    )


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
