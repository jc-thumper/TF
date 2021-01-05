# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        default['taxes_id'] = [(6, False, self.taxes_id.ids)]
        default['route_ids'] = [(6, False, self.route_ids.ids)]
        default['seller_ids'] = [(6, False, self.seller_ids.ids)]
        default['sale_ok'] = self.sale_ok
        default['purchase_ok'] = self.purchase_ok
        default['list_price'] = self.list_price
        default['standard_price'] = self.standard_price
        self = self.with_context(from_template=True)
        return super(ProductTemplate, self).copy(default=default)


    @api.onchange('uom_id', 'uom_po_id')
    def onchange_check_reordering_rule(self):
        if self.uom_id != self.uom_po_id:
            reordering_rule = self.env['stock.warehouse.orderpoint'].search(
                [('product_id.product_tmpl_id', '=', self._origin.id)])
            if reordering_rule and reordering_rule.qty_multiple <= 1:
                raise UserError(_('Warning ! \n Must have a Reordering rule with Quantity Multiple > 1.'))

    # def update_validation(self):
    #     for reorder in self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search([]):
    #         reorder.lead_days = 0
    #         reorder.lead_type = 'net'
    #     for price_list in self.env['product.supplierinfo'].with_context(active_test=False).search([]):
    #         if price_list.min_qty < 1 and price_list.delay < 1:
    #             price_list.write({'min_qty': 1,'delay': 1})
    #         if price_list.min_qty < 1:
    #             price_list.min_qty = 1
    #         if price_list.delay < 1:
    #             price_list.delay = 1
    #     for bom in self.env['mrp.bom'].with_context(active_test=False).search([]):
    #         bom.consumption = 'flexible'
    #         bom.ready_to_produce = 'asap'
    #     ir_model_data = self.env['ir.model.data']
    #     buy = ir_model_data.get_object_reference('purchase_stock', 'route_warehouse0_buy')[1]
    #     dropship = ir_model_data.get_object_reference('stock_dropshipping', 'route_drop_shipping')[1]
    #     manufacture = ir_model_data.get_object_reference('mrp', 'route_warehouse0_manufacture')[1]
    #     for each in self.env['product.template'].with_context(active_test=False).search([]):
    #         route_ids = each.route_ids.ids
    #         routes = route_ids and self.env['stock.location.route'].browse(route_ids).mapped('name') or []
    #
    #         if each.bom_count >= 1:
    #             if 'Buy' in routes:
    #                 each.write({'route_ids': [(3, buy)]})
    #             if 'Dropship' in routes:
    #                 each.write({'route_ids': [(3, dropship)]})
    #             each.write({'route_ids': [(4, manufacture)]})
    #
    #         if each.purchase_ok:
    #             each.write({'route_ids': [(4, buy)]})
    #         else:
    #             each.write({'route_ids': [(4, manufacture)]})
    #         if 'Dropship' in routes:
    #             each.write({'route_ids': [(4, buy)], 'sale_ok': True, 'purchase_ok': True})
    #         if each.weight == 0:
    #             each.write({'weight': 0.01})
    #         if each.sale_ok:
    #             default_customer_taxes = self.env.company.account_sale_tax_id.ids
    #             each.write({'taxes_id': [(6, 0, default_customer_taxes)]})
    #         else:
    #             each.write({'list_price': 0})
    #     return True

    def write(self, vals):
        for each in self:
            if not self.env.context.get("from_product"):
                product_type = vals.get('type', each.type)
                if vals.get('taxes_id'):
                    taxes_id = vals.get('taxes_id')[0][2]
                else:
                    taxes_id = each.taxes_id and each.taxes_id.ids or []
                if vals.get('route_ids'):
                    route_ids = vals.get('route_ids')[0][2]
                else:
                    route_ids = each.route_ids.ids
                sale_ok = vals.get('sale_ok', each.sale_ok)
                purchase_ok = vals.get('purchase_ok', each.purchase_ok)
                # bom_count = vals.get('bom_count') or each.bom_count
                # if vals.get('seller_ids'):
                #     seller_ids = vals.get('seller_ids')[0][2]
                # else:
                #     seller_ids = each.seller_ids.ids
                # standard_price = vals.get('standard_price', each.standard_price)
                lst_price = vals.get('lst_price', each.lst_price)
                if product_type in ['consu', 'product']:
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
                        # if len(routes) > 1:
                        #     if all(item in routes for item in ['Buy', 'Manufacture']):
                        #         raise UserError(_('Warning ! \n Cannot have both Buy & Manufacture.'))
                        # if bom_count >= 1 and 'Manufacture' not in routes:
                        #     raise UserError(_('Warning ! \n Route must be Manufacture since a BOM exists.'))

                        if sale_ok:
                            default_customer_taxes = self.env.company.account_sale_tax_id.ids
                            if not all(item in taxes_id for item in default_customer_taxes):
                                raise UserError(_('Warning ! \n When Can be Sold, Customer Taxes must be Texas'))
                            if not any(item in routes for item in ['Buy', 'Manufacture']):
                                raise UserError(_('Warning ! \n Route must be Buy or Manufacture'))
                            # if standard_price >= lst_price:
                            #     raise UserError(_('Warning ! \n Cost must be less than Sales price'))
                        else:
                            if lst_price > 0:
                                raise UserError(_('Warning ! \n Sales Price must be $0.00'))
                        if purchase_ok:
                            if 'Buy' not in routes:
                                raise UserError(_('Warning ! \n Route must be Buy since it can be purchased.'))
                            # if not seller_ids:
                            #     raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
                        else:
                            if 'Manufacture' not in routes:
                                raise UserError(_('Warning ! \n Route must be Manufacture since it cant be Purchased.'))
        self = self.with_context(from_template=True)
        res = super(ProductTemplate, self).write(vals)
        if vals.get('purchase_ok') or vals.get('seller_ids'):
            if self.purchase_ok and not self.seller_ids:
                raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
        return res

    @api.model
    def create(self, vals):
        self = self.with_context(from_template=True)
        res = super(ProductTemplate, self).create(vals)
        if not self.env.context.get("from_product"):
            if res.type in ['consu', 'product']:
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
                    # if len(res.route_ids) > 1:
                    #     if all(item in routes for item in ['Buy', 'Manufacture']):
                    #         raise UserError(_('Warning ! \n Cannot have both Buy & Manufacture.'))
                    # if res.bom_count > 1 and 'Manufacture' not in routes:
                    #     raise UserError(_('Warning ! \n Route must be Manufacture since a BOM exists.'))
                    if res.sale_ok:
                        default_customer_taxes = self.env.company.account_sale_tax_id.ids
                        taxes_id = res.taxes_id and res.taxes_id.ids or []
                        if not all(item in taxes_id for item in default_customer_taxes):
                            raise UserError(_('Warning ! \n When Can be Sold, Customer Taxes must be Texas'))
                        if not any(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Route must be Buy or Manufacture'))
                        # if res.standard_price >= res.list_price:
                        #     raise UserError(_('Warning ! \n Cost must be less than Sales price'))
                    else:
                        if res.lst_price > 0:
                            raise UserError(_('Warning ! \n Sales Price must be $0.00'))
                    if res.purchase_ok:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy since it can be purchased.'))
                        if not res.seller_ids:
                            raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
                    else:
                        if 'Manufacture' not in routes:
                            raise UserError(_('Warning ! \n Route must be Manufacture since it cant be Purchased.'))
        return res


class Product(models.Model):
    _inherit = "product.product"

    weight = fields.Float('Weight', digits='Stock Weight', default=0.01)

    @api.onchange('uom_id', 'uom_po_id')
    def onchange_check_reordering_rule(self):
        if self.uom_id != self.uom_po_id:
            reordering_rule = self.env['stock.warehouse.orderpoint'].search(
                [('product_id', '=', self._origin.id)])
            if reordering_rule and reordering_rule.qty_multiple <= 1:
                raise UserError(_('Warning ! \n Must have a Reordering rule with Quantity Multiple > 1.'))

    @api.model
    def create(self, vals):
        self = self.with_context(from_product=True)
        res = super(Product, self).create(vals)
        if not self.env.context.get("from_template"):
            if res.type in ['consu', 'product']:
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
                    # if len(res.route_ids) > 1:
                    #     if all(item in routes for item in ['Buy', 'Manufacture']):
                    #         raise UserError(_('Warning ! \n Cannot have both Buy & Manufacture.'))
                    # if res.bom_count > 1 and 'Manufacture' not in routes:
                    #     raise UserError(_('Warning ! \n Route must be Manufacture since a BOM exists.'))

                    if res.sale_ok:
                        default_customer_taxes = self.env.company.account_sale_tax_id.ids
                        taxes_id = res.taxes_id and res.taxes_id.ids or []
                        if not all(item in taxes_id for item in default_customer_taxes):
                            raise UserError(_('Warning ! \n When Can be Sold, Customer Taxes must be Texas'))
                        if not any(item in routes for item in ['Buy', 'Manufacture']):
                            raise UserError(_('Warning ! \n Route must be Buy or Manufacture'))
                        # if res.standard_price >= res.lst_price:
                        #     raise UserError(_('Warning ! \n Cost must be less than Sales price'))
                    else:
                        if res.lst_price > 0:
                            raise UserError(_('Warning ! \n Sales Price must be $0.00'))
                    if res.purchase_ok:
                        if 'Buy' not in routes:
                            raise UserError(_('Warning ! \n Route must be Buy since it can be purchased.'))
                        if not res.seller_ids:
                            raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
                    else:
                        if 'Manufacture' not in routes:
                            raise UserError(_('Warning ! \n Route must be Manufacture since it cant be Purchased.'))
        return res

    def write(self, vals):
        for each in self:
            if not self.env.context.get("from_template") and not self.env.context.get("from_product"):
                product_type = vals.get('type', each.type)
                if vals.get('taxes_id'):
                    taxes_id = vals.get('taxes_id')[0][2]
                else:
                    taxes_id = each.taxes_id and each.taxes_id.ids or []
                if vals.get('route_ids'):
                    route_ids = vals.get('route_ids')[0][2]
                else:
                    route_ids = each.route_ids.ids
                sale_ok = vals.get('sale_ok', each.sale_ok)
                purchase_ok = vals.get('purchase_ok', self.purchase_ok)
                # bom_count = vals.get('bom_count') or self.bom_count
                # if vals.get('seller_ids'):
                #     seller_ids = vals.get('seller_ids')[0][2]
                # else:
                #     seller_ids = self.seller_ids.ids
                # standard_price = vals.get('standard_price', self.standard_price)
                lst_price = vals.get('lst_price', self.lst_price)

                if product_type in ['consu', 'product']:

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
                        # if len(routes) > 1:
                        #     if all(item in routes for item in ['Buy', 'Manufacture']):
                        #         raise UserError(_('Warning ! \n Cannot have both Buy & Manufacture.'))
                        # if bom_count >= 1 and 'Manufacture' not in routes:
                        #     raise UserError(_('Warning ! \n Route must be Manufacture since a BOM exists.'))
                        if sale_ok:
                            default_customer_taxes = self.env.company.account_sale_tax_id.ids
                            if not all(item in taxes_id for item in default_customer_taxes):
                                raise UserError(_('Warning ! \n When Can be Sold, Customer Taxes must be Texas'))
                            if not any(item in routes for item in ['Buy', 'Manufacture']):
                                raise UserError(_('Warning ! \n Route must be Buy or Manufacture'))
                            # if standard_price >= lst_price:
                            #     raise UserError(_('Warning ! \n Cost must be less than Sales price'))
                        else:
                            if lst_price > 0:
                                raise UserError(_('Warning ! \n Sales Price must be $0.00'))
                        if purchase_ok:
                            if 'Buy' not in routes:
                                raise UserError(_('Warning ! \n Route must be Buy since it can be purchased.'))
                            # if not seller_ids:
                            #     raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
                        else:
                            if 'Manufacture' not in routes:
                                raise UserError(_('Warning ! \n Route must be Manufacture since it cant be Purchased.'))
        self = self.with_context(from_product=True)
        res = super(Product, self).write(vals)
        if vals.get('purchase_ok') or vals.get('seller_ids'):
            if self.purchase_ok and not self.seller_ids:
                raise UserError(_('Warning ! \n Must have a Vendor Pricelist.'))
        return res


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

    lead_type = fields.Selection(
        [('net', 'Days to get the products'), ('supplier', 'Days to purchase')], 'Lead Type',
        required=True, default='net')

    @api.constrains('qty_multiple', 'product_id')
    def _check_reordering_rule(self):
        for record in self:
            if record.product_id.uom_id != record.product_id.uom_po_id and record.qty_multiple <= 1:
                raise UserError(_('Warning ! \n Must have a Reordering rule with Quantity Multiple > 1.'))


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
