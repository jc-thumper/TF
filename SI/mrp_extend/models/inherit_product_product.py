# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_round

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    ###############################
    # GENERAL FUNCTIONS
    ###############################
    def get_BOM(self):
        """ The Function return the highest priority of BOMs for the current product variant

        :return: BOM record set if this product can be manufactured
        :rtype: Union[obj, None]
        """
        self.ensure_one()
        bom_id = None
        for bom in self.bom_ids:
            if bom.active:
                if not bom_id:
                    bom_id = bom
                # get the BOM has smallest sequence and biggest id
                elif bom_id.sequence > bom.sequence:
                    bom_id = bom

        return bom_id

    def get_open_mo_info_dict(self, warehouse_id=None):
        """ The function return the dictionary contain the open MO information of each products in product_variants

        :param int warehouse_id:
        :return:
        Ex: {
                product_id: {
                    'reserved_mo_qty': 0,
                    'open_mo_qty': 0,
                    'soonest_receive_mo_date': None,
                    'open_mo': None
                }
            }
        :rtype: dict
        """
        open_mo_info_dict = {}
        MO_will_receive_dict = self._compute_MO_will_receive_dict(
            self._context.get('owner_id'),
            warehouse_id
        )
        for product in self:
            product_id = product.id
            product_data = MO_will_receive_dict.get(product_id)
            open_mo_info_item = open_mo_info_dict.setdefault(product_id, {})
            if product_data:
                open_mo_info_item.update({
                    'reserved_mo_qty': product_data['be_reserved_qty'],
                    'open_mo_qty': product_data['will_receive_qty'],
                    'open_mo': product_data['open_mo']
                })
                if product.manufacturing:
                    open_mo_info_item['soonest_receive_mo_date'] = product_data['schedule_date']
                else:
                    open_mo_info_item['soonest_receive_mo_date'] = None
            else:
                open_mo_info_item.update({
                    'reserved_mo_qty': 0,
                    'open_mo_qty': 0,
                    'soonest_receive_mo_date': None,
                    'open_mo': None
                })
        return open_mo_info_dict

    def _compute_MO_will_receive_dict(self, owner_id=None, warehouse_id=None):
        """

        :param owner_id:
        :return: dictionary
        Ex: {
            product_id: {
                'will_receive_qty': 123,
                'schedule_date': Datetime
            }
        }
        :rtype: dict
        """
        res = {}
        _, domain_move_in_loc, domain_move_out_loc = self._get_domain_locations()

        product_ids = self.ids
        if product_ids:
            domain_move_in = [('product_id', 'in', product_ids)] + domain_move_in_loc
            domain_move_out = domain_move_out_loc

            if owner_id is not None:
                domain_move_in += [('restrict_partner_id', '=', owner_id)]
                domain_move_out += [('restrict_partner_id', '=', owner_id)]

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

                domain_move_in += [('location_dest_id', 'in', location_ids)]
                domain_move_out += [('location_dest_id', 'in', location_ids)]

            move_env = self.env['stock.move']
            domain_move_in_todo = [('production_id', '!=', None),
                                   ('production_id.state', 'in', ('confirmed', 'planned', 'progress')),
                                   ('state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available'))] \
                                  + domain_move_in

            # Step 1: Find the open move in for finish goods
            finish_good_move = move_env.search_read(domain_move_in_todo,
                                                    ['id', 'product_id', 'product_qty', 'production_id', 'date'])
            production_ids = [i['production_id'][0] for i in finish_good_move]
            move_in_ids = [i['id'] for i in finish_good_move]
            qty_done_dict = move_env.get_move_qty_dict(move_in_ids)
            move_in_qty_dict = {i['production_id'][0]: {
                'product_qty': i['product_qty'],
                'quantity_done': qty_done_dict[i['id']],
                'date': i['date'],
            } for i in finish_good_move}

            # Step 2: Find the corresponding move out for the materials
            domain_move_out_todo = [('raw_material_production_id', 'in', production_ids), ('scrapped', '=', False)]

            query = move_env._where_calc(domain_move_out_todo)
            move_env._apply_ir_rules(query, 'read')

            from_clause, where_clause, params = query.get_sql()
            query_str = """
                                        SELECT stock_move.id, product_id, raw_material_production_id
                                        FROM {}
                                        WHERE {}
                                    """.format(from_clause, where_clause)

            self.env.cr.execute(query_str, params)

            materials_moves = list(self._cr.dictfetchall())
            move_out_ids = [move['id'] for move in materials_moves]
            # The product_qty and quantity_done is in the stock_move's UoM
            move_out_qty_dict = move_env.get_move_qty_dict(move_out_ids)

            # Step 3: Create a dictionary with the format:
            # {
            #   production_id: {
            #       'bom_id': bom_id,
            #       'material': {
            #           pid_1: {
            #               'reserved_availability': 123
            #           }
            #       },
            #       'fg_id': 1
            #   }
            # }
            production_dict = {}
            for m in materials_moves:
                move_qty = move_out_qty_dict[m['id']]
                production_id = m['raw_material_production_id']
                production_item = production_dict.setdefault(production_id, {})
                if not production_item:
                    production_item['material'] = {}
                material_info = production_item['material'].setdefault(m['product_id'], {'reserved_availability': 0})
                material_info['reserved_availability'] = material_info['reserved_availability'] + move_qty['reserved_availability']

            # Step 4: embed production information to the production_dict
            product_mo_dict = {}
            if production_ids:
                production_info = self.env['mrp.production'] \
                    .search([('id', 'in', production_ids)])
                for p in production_info:
                    production_item = production_dict.setdefault(p.id, {})
                    production_item.setdefault('material', {})
                    production_item['bom_id'] = p.bom_id.id

                    product_id = p.product_id.id
                    production_item['fg_id'] = product_id
                    production_item['product_qty'] = p.product_uom_id. \
                        _compute_quantity(p.product_qty, p.product_id.uom_id)

                    product_mo_dict[p.id] = p

            # Step 5:
            product_bom_dict = self.env['mrp.bom'].build_bom_dict(self)
            for production_id, value in production_dict.items():
                # The production information
                material_qty_dict = value['material']

                fg_id = value['fg_id']
                product_qty = value['product_qty']
                if fg_id in product_ids:
                    fg_item = res.setdefault(fg_id, {
                        'be_reserved_qty': 0,
                        'will_receive_qty': 0,
                        'schedule_date': None,
                        'open_mo': None
                    })

                    open_mo_item = fg_item['open_mo']
                    if open_mo_item:
                        fg_item['open_mo'] = fg_item['open_mo'] + product_mo_dict.get(production_id)
                    else:
                        fg_item['open_mo'] = product_mo_dict.get(production_id)

                    # just get the BOM Information
                    bom_id = value['bom_id']
                    bom = product_bom_dict.get(bom_id, {})

                    # get maximum reserved_fg_qty base on requested qty of the finish good in move in section
                    # fg_id = value['fg_id']
                    move_in_fg_info = move_in_qty_dict.get(production_id)
                    reserved_fg_qty = move_in_fg_info['product_qty']
                    reserved_fg_date = move_in_fg_info['date']

                    try:
                        if bom:
                            # Loop each component in BOM structure and find the minimum reserved qty
                            bom_materials = bom.get('materials')
                            for material_id, material_data in bom_materials.items():
                                line = material_data['line']
                                product_line = material_data['product_line']
                                if line['choose_line_qty'] and product_line['active']:
                                    material_qty = material_qty_dict.get(material_id, {}).get('reserved_availability', 0) \
                                                   / material_data['qty']

                                    # The number of BOM user requested
                                    reserved_fg_qty = min(reserved_fg_qty, material_qty)

                            # Update res
                            fg_qty_dict = bom.get('finish_good')
                            be_reserved_qty = fg_item['be_reserved_qty'] + reserved_fg_qty * fg_qty_dict['qty']
                            will_receive_qty = fg_item['will_receive_qty'] + product_qty
                            rounding = fg_qty_dict['finish_uom_rounding']
                            cur_schedule_date = fg_item['schedule_date']

                            fg_item['be_reserved_qty'] = float_round(be_reserved_qty, precision_rounding=rounding)
                            fg_item['will_receive_qty'] = float_round(will_receive_qty, precision_rounding=rounding)
                            fg_item['schedule_date'] = reserved_fg_date \
                                if cur_schedule_date is None \
                                else min(cur_schedule_date, reserved_fg_date)

                        else:
                            rounding = 1.0
                            cur_schedule_date = fg_item['schedule_date']
                            fg_item['be_reserved_qty'] = float_round(fg_item['be_reserved_qty'] + product_qty, precision_rounding=rounding)
                            fg_item['will_receive_qty'] = float_round(fg_item['will_receive_qty'] + product_qty, precision_rounding=rounding)
                            fg_item['schedule_date'] = reserved_fg_date \
                                if cur_schedule_date is None \
                                else min(cur_schedule_date, reserved_fg_date)
                    except ValueError:
                        continue

        return res

    def _get_product_uom_of_manufacture(self, product_ids=None):
        """
        Get the factor of unit of measure of products used to create Manufacturing Order
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
                    product_uom.id as product_uom_id,
                    product_uom.factor as product_uom_factor,
                    mrp_bom.id as bom_id,
                    bom_uom.id as bom_uom_id,
                    bom_uom.factor as bom_uom_factor
                from product_product pp
                join product_template pt on pp.product_tmpl_id = pt.id
                join uom_uom product_uom on pt.uom_id = product_uom.id
                join mrp_bom on (mrp_bom.product_id = pp.id) or (mrp_bom.product_tmpl_id = pt.id and mrp_bom.product_id is NULL)
                join uom_uom bom_uom on mrp_bom.product_uom_id = bom_uom.id
                where 
                    pp.id in %s and mrp_bom.active is TRUE;
            """
            sql_params = (tuple(product_ids),)
            self.env.cr.execute(sql_query, sql_params)
            records = self.env.cr.dictfetchall()
            for item in records:
                result[item.get('product_id')] = item

        return result

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
