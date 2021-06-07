# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.tools import pycompat
from odoo.tools.float_utils import float_round
from odoo.addons.stock.models.product import Product

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_domain_locations(self):
        """
            Parses the context and returns a list of location_ids based on it.
            It will return all stock locations when no parameters are given
            Possible parameters are shop, warehouse, location, force_company, compute_child
        :return:
        """
        if self.env.context.get('company', False):
            if isinstance(self.env.context['company'], pycompat.integer_types):
                company_ids = [self.env.context['company']]
            elif isinstance(self.env.context['company'], pycompat.string_types):
                domain = [('name', 'ilike', self.env.context['company'])]
                company_ids = self.env['res.company'].search(domain).ids
            else:
                company_ids = self.env.context['company']

            return (
                [('location_id.company_id', 'in', company_ids), ('location_id.usage', 'in', ['internal', 'transit'])],
                ['&',
                     ('location_dest_id.company_id', 'in', company_ids),
                     '|',
                         ('location_id.company_id', '=', False),
                         '&',
                             ('location_id.usage', 'in', ['inventory', 'production']),
                             ('location_id.company_id', 'in', company_ids),
                 ],
                ['&',
                     ('location_id.company_id', 'in', company_ids),
                     '|',
                         ('location_dest_id.company_id', '=', False),
                         '&',
                             ('location_dest_id.usage', 'in', ['inventory', 'production']),
                             ('location_dest_id.company_id', 'in', company_ids),
                 ]
            )
        else:
            domain_quant_loc, domain_move_in_loc, domain_move_out_loc = super(ProductProduct, self)._get_domain_locations()

        # add a new to remove some locations when we calculate the quantity
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

    def get_product_name(self, product_ids=None, is_short_name=False):
        """
        Get name of products to display in sections in Inventory Dashboard
        :param product_ids: list of product id to get the name
        Default value is None. It means get name of all products
        :type product_ids: Union[None, int]
        :param is_short_name: if the product name is too long, we will
        show a short version of the name
        :type is_short_name: bool
        :return: a dictionary map product id to the name
        {
            <product_id>: "Product A",
        }
        """
        MAX_LENGTH_NAME = 40
        product_names = {}
        try:
            where_conditions = ""
            sql_params = []
            if product_ids is not None and product_ids:
                where_conditions = " where pp.id in %s"
                sql_params = [tuple(product_ids)]

            sql_query = """
                select
                    pp.id as product_id,
                    product_tmpl_id as template_id,
                    name as product_name
                from product_product pp
                join product_template pt on pt.id = pp.product_tmpl_id
            """
            sql_query += where_conditions
            self.env.cr.execute(sql_query, tuple(sql_params))
            records = self.env.cr.dictfetchall()

            if is_short_name is False:
                # get full name of product
                product_names = {item.get('product_id'): item.get('product_name') for item in records}
            else:
                # truncate the product name if it's too long
                for item in records:
                    item_name = item.get('product_name')
                    if len(item_name) > MAX_LENGTH_NAME:
                        item_name = item_name[0:30] + '... ' + item_name[-8:]

                    product_names[item.get('product_id')] = item_name

        except Exception as e:
            _logger.exception("Error when _get_product_name.", exc_info=True)
            raise e

        return product_names


# Out of class Product.Product
def _compute_quantities_dict(self, lot_id, owner_id, package_id, from_date=False, to_date=False):
    """

    :param self:
    :param lot_id:
    :param owner_id:
    :param package_id:
    :param from_date:
    :param to_date:
    :return dict:
    Ex: {
            product_id: {
                'qty_available': 123.455,
                'incoming_qty': 121.21,
                'outgoing_qty': 232.12,
                'virtual_available': 423
            }
        }
    """
    res = dict()
    product_ids = self.ids
    if not product_ids:
        return res

    domain_quant_loc, domain_move_in_loc, domain_move_out_loc = self._get_domain_locations()
    domain_quant = [('product_id', 'in', product_ids)] + domain_quant_loc
    dates_in_the_past = False
    # only to_date as to_date will correspond to qty_available
    to_date = fields.Datetime.to_datetime(to_date)
    if to_date and to_date < fields.Datetime.now():
        dates_in_the_past = True

    domain_move_in = [('product_id', 'in', product_ids)] + domain_move_in_loc
    domain_move_out = [('product_id', 'in', product_ids)] + domain_move_out_loc
    if lot_id is not None:
        domain_quant += [('lot_id', '=', lot_id)]
    if owner_id is not None:
        domain_quant += [('owner_id', '=', owner_id)]
        domain_move_in += [('restrict_partner_id', '=', owner_id)]
        domain_move_out += [('restrict_partner_id', '=', owner_id)]
    if package_id is not None:
        domain_quant += [('package_id', '=', package_id)]
    if dates_in_the_past:
        domain_move_in_done = list(domain_move_in)
        domain_move_out_done = list(domain_move_out)
    if from_date:
        domain_move_in += [('date', '>=', from_date)]
        domain_move_out += [('date', '>=', from_date)]
    if to_date:
        domain_move_in += [('date', '<=', to_date)]
        domain_move_out += [('date', '<=', to_date)]

    move_env = self.env['stock.move']
    quant_env = self.env['stock.quant']
    domain_move_in_todo = [(
        'state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_in
    domain_move_out_todo = [('state', 'in',
                             ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_out
    moves_in_res = dict((item['product_id'][0], item['product_qty']) for item in
                        move_env.read_group(domain_move_in_todo, ['product_id', 'product_qty'], ['product_id'],
                                            orderby='id'))
    moves_out_res = dict((item['product_id'][0], item['product_qty']) for item in
                         move_env.read_group(domain_move_out_todo, ['product_id', 'product_qty'], ['product_id'],
                                             orderby='id'))
    quants_res = dict((item['product_id'][0], item['quantity']) for item in
                      quant_env.read_group(domain_quant, ['product_id', 'quantity'], ['product_id'], orderby='id'))
    if dates_in_the_past:
        # Calculate the moves that were done before now to calculate back in time
        # (as most questions will be recent ones)
        domain_move_in_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_in_done
        domain_move_out_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_out_done
        moves_in_res_past = dict((item['product_id'][0], item['product_qty']) for item in
                                 move_env.read_group(domain_move_in_done, ['product_id', 'product_qty'], ['product_id'],
                                                     orderby='id'))
        moves_out_res_past = dict((item['product_id'][0], item['product_qty']) for item in
                                  move_env.read_group(domain_move_out_done, ['product_id', 'product_qty'], ['product_id'],
                                                      orderby='id'))

    self._cr.execute("""
                        SELECT pp.id as id, pt.uom_id 
                        FROM product_product pp 
                            JOIN product_template pt ON pp.product_tmpl_id = pt.id 
                        WHERE pp.id in %s""", (tuple(product_ids),))
    products = [product for product in self._cr.dictfetchall()]
    uom_ids = [product['uom_id'] for product in products]
    uom_dict = dict((uom['id'], uom['rounding']) for uom in
                    self.env['uom.uom'].search_read([('id', 'in', uom_ids)], ['id', 'rounding']))
    for product in products:
        product_id = product['id']
        uom_id = product['uom_id']
        rounding = uom_dict[uom_id]
        product_qty_dict = res.setdefault(product_id, {})
        if dates_in_the_past:
            qty_available = quants_res.get(product_id, 0.0) \
                            - moves_in_res_past.get(product_id, 0.0) \
                            + moves_out_res_past.get(product_id, 0.0)
        else:
            qty_available = quants_res.get(product_id, 0.0)

        incoming_qty = float_round(moves_in_res.get(product_id, 0.0), precision_rounding=rounding)
        outgoing_qty = float_round(moves_out_res.get(product_id, 0.0), precision_rounding=rounding)

        product_qty_dict['qty_available'] = float_round(qty_available, precision_rounding=rounding)
        product_qty_dict['incoming_qty'] = incoming_qty
        product_qty_dict['outgoing_qty'] = outgoing_qty
        product_qty_dict['virtual_available'] = float_round(qty_available + incoming_qty - outgoing_qty,
                                                            precision_rounding=rounding)

    return res


Product._compute_quantities_dict = _compute_quantities_dict
