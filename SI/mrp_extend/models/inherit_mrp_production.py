# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    ###############################
    # HELPER FUNCTION
    ###############################
    def get_manufacturing_order_data(self, company_id, warehouse_id=None, product_ids=None):
        """
            Get all the MOs in current warehouse with state not in (done, cancel)
        :param int company_id:
        :return: (list[int] mo_ids, dict mo_dict)
        """

        # Create an manufacturing_order_dict
        # {
        #     manufacturing_order_id: {
        #       'produced_product_id' : mo.product_id.id
        #       'bom_id': mo.bom_id.id
        #     }
        # }
        query = """
            SELECT id, product_id, bom_id 
            FROM mrp_production
            WHERE state NOT IN ('done', 'cancel')
              AND
                  company_id = %(company_id)s
        """

        query_params = {
            'company_id': company_id
        }

        if warehouse_id is not None:
            location_ids = self.env['stock.location'].get_all_locations_of_warehouse(
                warehouse_id=warehouse_id,
                company_id=self.env.user.company_id.id,
                is_excluded_location=True
            )

            query += """
                AND
                    location_dest_id in %(location_ids)s
            """
            query_params.update({
                'location_ids': tuple(location_ids)
            })

        if product_ids is not None:
            query += """
                AND
                    product_id in %(product_ids)s
            """
            query_params.update({
                'product_ids': tuple(product_ids)
            })

        self._cr.execute(query, query_params)
        data = self._cr.dictfetchall()

        mo_ids = []
        mo_dict = {}
        for line in data:
            mo_item = mo_dict.setdefault(line.get('id'), {})
            mo_item['produced_product_id'] = line.get('product_id')
            mo_item['bom_id'] = line.get('bom_id')

            mo_ids.append(line.get('id'))

        return mo_ids, mo_dict