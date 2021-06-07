# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_round

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_product_uom_dict(self):
        """

        :return:
        Ex: {
                product_id: uom_id
            }
        :rtype: dict
        """
        product_uom_dict = {}
        product_ids = self.ids
        if product_ids:
            query = """
                SELECT pp.id, pt.uom_id
                FROM product_product pp
                    JOIN product_template pt
                        ON pp.product_tmpl_id = pt.id
                WHERE pp.id in %s"""
            self._cr.execute(query, (tuple(product_ids),))
            for product_uom in self._cr.dictfetchall():
                product_uom_dict[product_uom['id']] = product_uom['uom_id']
        return product_uom_dict

    def _get_product_uom(self, product_ids=None):
        """
        Get the factor of unit of measure of products
        :param product_ids: List of product id to get the factor
        :type product_ids: List[int]
        :return:
        {
            <product_id>: {
                'uom_id': <int>,
                'factor': <float>
            },
            ...
        }
        :rtype: dict
        """
        result = {}
        if product_ids:
            sql_query = """
                select
                    pp.id as product_id,
                    pt.id as template_id,
                    pt.uom_id,
                    uu.factor
                from product_product pp
                join product_template pt on pp.product_tmpl_id = pt.id
                join uom_uom uu on uu.id = pt.uom_id
                where pp.id in %s;
            """
            sql_params = (tuple(product_ids),)
            self.env.cr.execute(sql_query, sql_params)
            records = self.env.cr.dictfetchall()
            for item in records:
                result[item.get('product_id')] = item

        return result

    def get_actual_available_qty_dict(self, warehouse_id=None):
        """ compute from qty_available - reserved_quantity

        :return:
        :rtype: dict
        """
        actual_available_qty_dict = {}
        res = self._compute_reserved_quantity_dict(self._context.get('lot_id'),
                                                   self._context.get('owner_id'),
                                                   self._context.get('package_id'),
                                                   warehouse_id)
        for product in self:
            product_id = product.id
            free_qty = max(res[product_id]['qty_available'] - res[product_id]['reserved_quantity'], 0)
            actual_available_qty_dict[product_id] = free_qty

        return actual_available_qty_dict

    def _compute_reserved_quantity_dict(self, lot_id, owner_id, package_id, warehouse_id=None):
        """

        :param lot_id:
        :param owner_id:
        :param package_id:
        :return dict:
        """
        domain_quant_loc, _, _ = self._get_domain_locations()
        domain_quant = [('product_id', 'in', self.ids)] + domain_quant_loc
        # only to_date as to_date will correspond to qty_available
        if lot_id is not None:
            domain_quant += [('lot_id', '=', lot_id)]
        if owner_id is not None:
            domain_quant += [('owner_id', '=', owner_id)]
        if package_id is not None:
            domain_quant += [('package_id', '=', package_id)]
        if warehouse_id is not None:
            warehouse = self.env['stock.warehouse'].search([
                ('id', '=', warehouse_id)
            ], limit=1)
            warehouse = warehouse or self.env.user.company_id.default_warehouse

            warehouse_id = warehouse.id
            company_id = warehouse.company_id.id

            location_ids = self.env['stock.location'].get_all_locations_of_warehouse(
                warehouse_id=warehouse_id,
                company_id=company_id,
                is_excluded_location=True
            )
            domain_quant += [('location_id', 'in', location_ids)]

        quant_env = self.env['stock.quant']
        quants_res = dict((item['product_id'][0], (item['quantity'], item['reserved_quantity']))
                          for item in quant_env.read_group(domain_quant,
                                                           ['product_id', 'reserved_quantity', 'quantity'],
                                                           ['product_id'], orderby='id'))

        res = dict()
        for product in self.with_context(prefetch_fields=False):
            product_id = product.id
            rounding = product.uom_id.rounding
            res[product_id] = {}
            qty_available = quants_res.get(product_id, (0.0, None))[0]
            reserved_quantity = quants_res.get(product_id, (None, 0.0))[1]
            res[product_id]['reserved_quantity'] = float_round(reserved_quantity,
                                                               precision_rounding=rounding)
            res[product_id]['qty_available'] = float_round(qty_available,
                                                           precision_rounding=rounding)

        return res

    def _get_domain_locations(self):
        """ Parses the context and returns a list of location_ids based on it.
        It will return all stock locations when no parameters are given
        Possible parameters are shop, warehouse, location, force_company, compute_child

        :return:
        """
        domain_quant_loc, domain_move_in_loc, domain_move_out_loc = super(ProductProduct, self). \
            _get_domain_locations()
        exclude_locations = self.env.context.get('exclude_locations')
        if exclude_locations and isinstance(exclude_locations, list):
            domain_quant_loc += [
                ('location_id.id', 'not in', exclude_locations)]
            domain_move_in_loc += [
                ('location_id.id', 'not in', exclude_locations),
                ('location_dest_id.id', 'not in', exclude_locations)]
            domain_move_out_loc += [
                ('location_id.id', 'not in', exclude_locations),
                ('location_dest_id.id', 'not in', exclude_locations)]
        return domain_quant_loc, domain_move_in_loc, domain_move_out_loc