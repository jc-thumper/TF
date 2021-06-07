# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    ###############################
    # GENERAL FUNCTION
    ###############################
    def get_acceptable_bom(self, bom_ids):
        return self.search([('id', 'in', bom_ids)])

    def get_bom_structure_dict(self):
        """

        :return:
        Ex: {
            'product_id': 1,
            'product_qty': product_qty,
            'product_uom_id_factor': product_uom_id_factor,
            'product_qty_std': product_qty / product_uom_id_factor,
            'lines': {
                material_id: {
                    'material_id': material_id,
                    'material_uom_factor': material.uom_id.factor,
                    'bom_line_factor': bom_line_factor,
                    'bom_line_qty': bom_line_qty,
                    'choose_line_qty': choose_line_qty,
                    'product_active': material.active,
                    'bom_line_qty_std': bom_line_qty/bom_line_factor
                }
            }
        }
        :rtype: dict
        """
        self.ensure_one()
        product_qty = self.product_qty
        product_uom_id_factor = self.product_uom_id.factor
        structure_dict = {
            'bom_id': self.id,
            'product_qty': product_qty,
            'product_uom_id_factor': product_uom_id_factor,
            'product_qty_std': product_qty / product_uom_id_factor,
        }
        lines = {}

        for bom_line in self.bom_line_ids:
            material = bom_line.product_id
            choose_line_qty = bom_line.choose_line_qty
            material_id = material.id
            bom_line_factor = bom_line.product_uom_id.factor
            bom_line_qty = bom_line.product_qty
            lines[material_id] = {
                'material_id': material_id,
                'material_uom_factor': material.uom_id.factor,
                'bom_line_factor': bom_line_factor,
                'bom_line_qty': bom_line_qty,
                'choose_line_qty': choose_line_qty,
                'product_active': material.active,
                'bom_line_qty_std': bom_line_qty / bom_line_factor
            }
        structure_dict.update({'lines': lines})

        return structure_dict

    def build_bom_dict(self, products):
        """

        :param products:
        :type products: ProductProduct
        :return: a dictionary contain bom information
        Ex: {
            'bom': bom,
            'finish_good': {
                'product': bom.product_id,
                'product_id': bom.product_id.id,
                'qty': bom.product_qty * bom.product_id.uom_id.factor / bom.product_uom_id.factor
            },
            'materials': {
                material_id: {
                    'material': material,
                    'qty': line.product_qty * material.uom_id.factor / line.product_uom_id.factor,
                    'line': line
                }
            }
        }
        :rtype: dict
        """
        product_bom_dict = {}

        # Step 1: Get/Generate PRODUCT VARIANTS information dictionary
        product_ids = products.ids
        if product_ids:
            products_values = []
            self._cr.execute("SELECT id, product_tmpl_id FROM product_product WHERE id in %s", (tuple(product_ids),))
            for line in self._cr.dictfetchall():
                products_values.append(line)

            # Step 2: Get/Generate corresponding PRODUCT TEMPLATES information dictionary
            product_tmpl_ids = [product['product_tmpl_id'] for product in products_values]
            product_tmpl_dict = dict([(p['id'], p['product_tmpl_id']) for p in products_values])

            # Step 3: From Product template+Variant get corresponding BOM
            self._cr.execute("""
                                    SELECT mrp_bom.id, product_id, product_tmpl_id, product_qty, product_uom_id
                                    FROM mrp_bom 
                                      JOIN mrp_routing m2 
                                        ON mrp_bom.routing_id = m2.id
                                    WHERE product_tmpl_id IN %s 
                            """, (tuple(product_tmpl_ids),))
            boms = [bom for bom in self._cr.dictfetchall()]

            bom_ids = [b['id'] for b in boms]
            bom_line_ids = []

            if bom_ids:
                # Step 4: Get corresponding BOM line
                self._cr.execute("""
                        SELECT id, bom_id, product_id, product_qty, product_uom_id, choose_line_qty
                        FROM mrp_bom_line 
                        WHERE bom_id IN %s""", (tuple(bom_ids),))
                product_line_ids = []
                for line in self._cr.dictfetchall():
                    bom_line_ids.append(line)
                    product_line_ids.append(line['product_id'])

                # Step 5: Get corresponding Product in BOM line
                product_line_dict = {}
                if product_line_ids:
                    self._cr.execute("""
                                    SELECT id, active
                                    FROM product_product 
                                    WHERE id IN %s""", (tuple(product_line_ids),))
                    product_line_dict = {prod['id']: prod for prod in self._cr.dictfetchall()}

                # Step 6: Get Product information in BOM line
                materials = []
                bom_line_dict = {}
                for line in bom_line_ids:
                    materials.append(line['product_id'])
                    bom_line = bom_line_dict.setdefault(line['bom_id'], [])
                    bom_line.append(line)

                # Step 7: Get Product Template and BOM information of remain product
                all_products = list(set(materials + product_ids))
                if all_products:
                    self._cr.execute("""
                                    SELECT pp.id, pt.id, pt.uom_id 
                                    FROM product_template pt 
                                    JOIN product_product pp 
                                    ON pt.id = pp.product_tmpl_id 
                                    WHERE pp.id in %s
                                    """, (tuple(all_products),))

                tmpl_uom_dict = {}
                for product_id, template_id, uom_id in self._cr.fetchall():
                    product_tmpl_dict[product_id] = template_id
                    tmpl_uom_dict[template_id] = uom_id

                # uom_ids = list(tmpl_uom_dict.values())
                uoms = self.env['uom.uom'].search_read([], ['id', 'rounding', 'factor'])
                uom_dict = dict([(uom['id'], {'rounding': uom['rounding'], 'factor': uom['factor'], }) for uom in uoms])

                for bom in boms:
                    bom_id = bom['id']
                    product_id = bom.get('product_id')
                    product_tmpl_id = bom.get('product_tmpl_id')
                    finish_uom_id = product_id and tmpl_uom_dict[product_tmpl_dict[product_id]] or tmpl_uom_dict[
                        product_tmpl_id]
                    finish_uom_rounding = uom_dict[finish_uom_id]['rounding']
                    finish_uom_factor = uom_dict[finish_uom_id]['factor']
                    bom_product_uom_factor = uom_dict[bom['product_uom_id']]['factor']
                    bom_dict = {
                        'finish_good': {
                            'finish_uom_rounding': finish_uom_rounding,
                            'qty': bom['product_qty'] * finish_uom_factor / bom_product_uom_factor
                        },
                        'materials': {}
                    }

                    material_dict = bom_dict['materials']

                    for line in bom_line_dict.get(bom_id, []):
                        material_id = line['product_id']
                        material_uom_id = tmpl_uom_dict[product_tmpl_dict[material_id]]
                        line_uom_id = line['product_uom_id']

                        material_dict[material_id] = {
                            'qty': line['product_qty'] * uom_dict[material_uom_id]['factor'] / uom_dict[line_uom_id][
                                'factor'],
                            'line': line,
                            'product_line': product_line_dict[material_id]
                        }

                    product_bom_dict.update({
                        bom_id: bom_dict
                    })

        return product_bom_dict
