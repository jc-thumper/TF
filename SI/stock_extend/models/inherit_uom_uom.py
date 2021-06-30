# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class UomUom(models.Model):
    _inherit = 'uom.uom'

    ###############################
    # GENERAL FUNCTIONS
    ###############################
    def get_uom_dict(self, domain=None):
        """

        :param domain:
        :return:
        Ex: {
                id: {
                    'id': 2
                    'factor': 0.1,
                    'rounding': 0.01,
                    'active': true
                }
            }
        :rtype: dict
        """
        uom_dict = {}
        domain = domain or []
        query = self._where_calc(domain)
        from_clause, where_clause, params = query.get_sql()
        query_str = """
                        SELECT id, factor, rounding, active
                        FROM {}
                        WHERE {}
                    """.format(from_clause, where_clause)
        self.env.cr.execute(query_str, params)
        for item in self.env.cr.dictfetchall():
            uom_dict[item['id']] = item
        return uom_dict