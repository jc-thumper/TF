# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ProductBOMInfo(models.Model):
    _name = "product.bom.info"
    _description = "Product Used In Information"
    _order = "mo_level, mo_path"

    ###############################
    # CONST
    ###############################

    ###############################
    # DEFAULT FUNCTIONS
    ###############################

    ###############################
    # FIELDS
    ###############################
    product_id = fields.Many2one('product.product', string='Raw material', required=True, readonly=True)
    bom_id = fields.Many2one('mrp.bom', string='BoM for Finished Product', required=True, readonly=True)
    bom_code = fields.Char(string=_('Build of Material Reference'), related='bom_id.code', readonly=True)
    intermediate_product_id = fields.Many2one('product.product', string=_('Intermediate Product'),
                                              required=False, readonly=True,
                                              help='This is the semi-product between the material is the current '
                                                   'product and the Finished Product using the Intermediate'
                                                   'as a material in BoM for Finished Product')
    target_product_id = fields.Many2one('product.product', string=_('Finished Product'),
                                        required=True, readonly=True,
                                        help='This is the product that is using the current product to manufacture')
    mo_level = fields.Integer(string=_('MO Level'), required=True, readonly=True)
    material_factor = fields.Float(required=True, readonly=True)
    produce_delay = fields.Integer(string=_('Total Produce Dates'), required=True, readonly=True, default=True)
    mo_path = fields.Char(string=_('MO Path'), required=True, readonly=True)
    active = fields.Boolean(required=True, readonly=True, default=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id.id)

    _sql_constraints = [
        ('product_route_uniq', 'unique(mo_path, company_id)',
         'Keep Constraints check the MO Paths should be Unique on a Company.'),
    ]

    @api.model_cr
    def init(self):
        self._cr.execute("""SELECT indexname FROM pg_indexes WHERE indexname = 'used_in_comp_mo_path'""")
        if not self._cr.fetchone():
            self._cr.execute(
                """CREATE INDEX used_in_comp_mo_path ON product_bom_info (mo_path, company_id)""")

    ###############################
    # PRIVATE FUNCTIONS
    ###############################
    def _update_boms_using_in(self, product_id, product_dict, intermediate_product_id, mo_path,
                              material_factor, produce_delay, level=2):
        """ The function update the dictionary product_dict with the deeper level

        :type product_id: int
        :param product_dict:
        :type intermediate_product_id: int
        :param level:
        :return:
        """
        used_in_boms = product_dict.get(intermediate_product_id)
        product_boms = product_dict.get(product_id)
        if used_in_boms and product_boms:
            for bom in used_in_boms:
                bom_level = bom['level']
                if bom_level == 1:
                    bom_structure = bom['bom_structure']
                    fg_id = bom_structure['product_id']
                    cur_factor = bom['material_factor']
                    cur_produce_delay = bom['produce_delay']
                    new_mo_path = '%s/%s' % (mo_path, fg_id)
                    product_boms.append({
                        'bom_structure': bom_structure,
                        'level': level,
                        'intermediate': intermediate_product_id,
                        'material_factor': material_factor * cur_factor,
                        'mo_path': new_mo_path,
                        'produce_delay': produce_delay + cur_produce_delay
                    })
                    self._update_boms_using_in(product_id, product_dict, fg_id, new_mo_path,
                                               material_factor * cur_factor, produce_delay + cur_produce_delay, level+1)

    def _update_to_records(self, product_dict, company):
        """

        :type product_dict: dict
        :type company: ResCompany
        :return:
        """
        # Archive all
        self.env.cr.execute("""UPDATE product_bom_info SET active = False WHERE company_id = %s""", (company.id, ))
        self.env.cr.commit()

        write_data = []

        for product_id, boms in product_dict.items():
            for bom in boms:
                bom_structure = bom['bom_structure']
                write_data.append({
                    'product_id': product_id,
                    'bom_id': bom_structure['bom_id'],
                    'intermediate_product_id': bom['intermediate'],
                    'target_product_id': bom_structure['product_id'],
                    'mo_level': bom['level'],
                    'material_factor': bom['material_factor'],
                    'produce_delay': bom['produce_delay'],
                    'company_id': company.id,
                    'mo_path': bom['mo_path'],
                    'uid': self._uid
                })

        sql_query = """
                        INSERT INTO product_bom_info (product_id, bom_id, intermediate_product_id, 
                            target_product_id, mo_level, material_factor, mo_path, produce_delay, company_id, active,
                            create_uid, write_uid, create_date, write_date)
                            VALUES (%(product_id)s, %(bom_id)s, %(intermediate_product_id)s, 
                            %(target_product_id)s, %(mo_level)s, %(material_factor)s, %(mo_path)s, 
                            %(produce_delay)s, %(company_id)s, True,
                            %(uid)s, %(uid)s, now() at time zone 'UTC', now() at time zone 'UTC')
                        ON CONFLICT (mo_path, company_id) DO UPDATE SET 
                            active = True,
                            bom_id = EXCLUDED.bom_id,
                            mo_level = EXCLUDED.mo_level,
                            material_factor = EXCLUDED.material_factor,
                            write_uid = EXCLUDED.write_uid,
                            write_date = EXCLUDED.write_date;
                    """
        self.env.cr.executemany(sql_query, write_data)
        self.env.cr.commit()

    ###############################
    # CRON FUNCTIONS
    ###############################
    @api.model
    def cron_update_products_are_used_in(self):
        """

        :return:
        product_dict example:
        {
            product_id: [{
                    'bom_structure': bom_structure,
                    'level': 1,
                    'intermediate': ProductProduct,
                    'material_factor': line_info['bom_line_qty_std'],
                    'mo_path': '%s/%s' % (material_id, product_id)
                }, ...]
        }
        """
        product_ids = self.env['product.product'].search([])
        bom_env = self.env['mrp.bom']
        company_ids = self.env['res.company'].search([])
        for company in company_ids:
            if company.id != 1:
                continue
            product_dict = {}
            material_ids = set()
            for prod in product_ids:
                product_id = prod.id
                produce_delay = prod.produce_delay

                # bom_id = prod.get_BOM()
                bom_id = bom_env._bom_find(product=prod, company_id=company.id)

                if bom_id:
                    bom_structure = bom_id.get_bom_structure_dict()
                    bom_structure['product_id'] = product_id

                    lines = bom_structure.get('lines', {})
                    for material_id, line_info in lines.items():
                        material_ids.add(material_id)
                        material_used_in_BoMs = product_dict.setdefault(material_id, [])
                        bom_info = {
                            'bom_structure': bom_structure,
                            'level': 1,
                            'intermediate': None,
                            'material_factor': line_info['bom_line_qty_std'],
                            'mo_path': '%s/%s' % (material_id, product_id),
                            'produce_delay': produce_delay
                        }
                        material_used_in_BoMs.append(bom_info)

            for product_id in material_ids:
                material_used_in_BoMs = product_dict.setdefault(product_id, [])
                for bom_dict in material_used_in_BoMs:
                    level = bom_dict['level']
                    if level == 1:
                        bom_structure = bom_dict['bom_structure']
                        target_product_id = bom_structure['product_id']
                        mo_path = bom_dict['mo_path']
                        material_factor = bom_dict['material_factor']
                        produce_delay = bom_dict['produce_delay']
                        self._update_boms_using_in(product_id, product_dict, target_product_id,
                                                   mo_path, material_factor, produce_delay, level=2)

            self._update_to_records(product_dict, company)
