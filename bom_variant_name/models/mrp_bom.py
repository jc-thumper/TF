# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def name_get(self):
        return [(bom.id, '%s%s' % (bom.code and '%s: ' % bom.code or '', bom.product_id.display_name or bom.product_tmpl_id.display_name)) for bom in self]


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
