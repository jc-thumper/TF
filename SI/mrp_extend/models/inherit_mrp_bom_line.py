# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    ###############################
    # FIELDS
    ###############################
    choose_line_qty = fields.Boolean(string="Choose line Quantity", default=True)

    ###############################
    # HELPER FUNCTION
    ###############################
    def get_not_choose_line_qty_bom_line_dict(self, product_ids):
        """
            Get the not set choose_line_qty for the material in BoM
        :param list[int] product_ids:

        :return: dict not_choose_line_qty_dict
            {
                (product_id, bom_id): True
            }

            "(product_id, bom_id): True" means that product has this product_id in bom
            whose id = bom_id is not checked choose_line_qty field.

        :rtype: dict
        """
        not_choose_line_qty_dict = {}

        if product_ids:
            query = """
                        SELECT product_id, bom_id
                        FROM mrp_bom_line
                            JOIN product_product ON mrp_bom_line.product_id = product_product.id
                        WHERE product_id in %(product_ids)s
                          AND
                              (choose_line_qty = false OR product_product.active = false);
                    """

            query_params = {
                'product_ids': tuple(product_ids),
            }

            self._cr.execute(query, query_params)
            data = self._cr.dictfetchall()

            for line in data:
                not_choose_line_qty_dict.setdefault(
                    (line.get('product_id'), line.get('bom_id')), True
                )

        return not_choose_line_qty_dict
