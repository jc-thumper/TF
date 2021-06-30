# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    ###############################
    # GENERAL FUNCTIONS
    ###############################

    def get_move_qty_dict(self, move_ids):
        """ Function return the dictionary contain quantity move done and reserved availability quantity

        :type move_ids: list[int]
        :return:
        {
            move_id: {
                'product_uom': product_uom,
                'reserved_availability': Total of product_qty of all stock_move's lines,

            }
        }
        """
        move_qty_dict = {}
        if move_ids:

            # Step 1: Generate the dictionary contain the move quantity
            self._cr.execute("""
                            SELECT move_id, SUM(product_qty) as sum_product_qty
                            FROM stock_move_line 
                            WHERE move_id IN %s 
                            GROUP BY move_id""", (tuple(move_ids),))
            result = {data['move_id']: data['sum_product_qty'] for data in self._cr.dictfetchall()}

            # Step 2: Generate the UoM dictionary
            uom_dict = {uom.id: uom for uom in self.env['uom.uom'].search([])}

            # Step 3: Generate the dictionary stock move and list of corresponding lines
            self._cr.execute("""
                            SELECT id, move_id, product_uom_id, qty_done FROM stock_move_line WHERE move_id IN %s
                    """, (tuple(move_ids),))
            """ line_dict = {
                    line_id: [
                        {
                            'id': 123,
                            'move_id': 111,
                            'product_uom_id': 1
                            'qty_done': 12.34
                        }, ...
                    ]
                }

                move_dict = {
                    move_id: [line1, line2,...]
                }
            """
            line_dict = {}
            move_dict = {}
            for line in self._cr.dictfetchall():
                line_id = line['id']
                line_dict.setdefault(line_id, line)
                move = move_dict.setdefault(line['move_id'], [])
                move.append(line_id)

            self._cr.execute("""SELECT id, product_uom, product_id FROM stock_move WHERE id in %s""",
                             (tuple(move_ids),))
            product_ids = []
            product_move_dict = {}
            for move in self._cr.dictfetchall():
                move_id = move['id']
                lines = move_dict.get(move_id, [])
                move_uom = uom_dict.get(move['product_uom'])
                quantity_done = 0
                for line_id in lines:
                    line = line_dict[line_id]
                    quantity_done += uom_dict[line['product_uom_id']]._compute_quantity(line['qty_done'], move_uom,
                                                                                        round=False)
                product_id = move['product_id']
                product_ids.append(product_id)
                product_move_dict.setdefault(product_id, []).append((move_id, move_uom))
                move_qty_dict[move_id] = {
                    'quantity_done': quantity_done,
                    'uom_id': move.get('product_uom')
                }

            self._cr.execute("""
                            SELECT pp.id as product_id, pt.uom_id 
                            FROM product_product pp 
                                JOIN product_template pt ON pp.product_tmpl_id = pt.id 
                            WHERE pp.id in %s""", (tuple(product_ids),))
            for product_id, uom_id in self._cr.fetchall():
                for move_id, move_uom in product_move_dict.get(product_id, []):
                    reserved_availability = uom_dict[uom_id]._compute_quantity(result.get(move_id, 0.0),
                                                                               move_uom,
                                                                               rounding_method='HALF-UP')
                    move_qty_dict[move_id]['reserved_availability'] = reserved_availability

        return move_qty_dict
