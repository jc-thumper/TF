# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def write(self, vals):
        if not vals.get('active', False):
            self.env['mrp.bom'].sudo().search([('product_tmpl_id', 'in', self.ids)]).write({'active': False})
        return super(ProductTemplate, self).write(vals)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def name_get(self):
        result = super(ProductProduct, self).name_get()

        archived_product_ids = self.filtered(lambda rec: not rec.active).ids
        for i, rec in enumerate(result):
            if rec[0] in archived_product_ids and 'ARCV:' not in rec[1]:
                result[i] = (rec[0], "ARCV: %s" % rec[1])

        return result

    def write(self, vals):
        if not vals.get('active', False):
            self.mapped('orderpoint_ids').write({'active': False})
            self.env['mrp.bom'].sudo().search([('product_id', 'in', self.ids)]).write({'active': False})

        return super(ProductProduct, self).write(vals)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
