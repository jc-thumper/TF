# -*- encoding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def write(self, vals):
        if not vals.get('active', True):
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
        if not vals.get('active', True):
            product_available = self._product_available()
            for product in self:
                if product_available.get(product.id, {}).get('qty_available', 0):
                    raise UserError("Action cannot be performed as Product %s has stock available." % (product.display_name))

                open_so = self.env['sale.order'].sudo().search([('state', 'in', ['draft', 'sent']), ('order_line.product_id', '=', product.id)])
                if open_so:
                    ref = ", ".join(open_so.mapped('name'))
                    raise UserError("The product %s could not be archived because of an open Sale Order (%s)" % (product.display_name, ref))

                open_po = self.env['purchase.order'].sudo().search([('state', 'in', ['draft', 'sent', 'to approve']), ('order_line.product_id', '=', product.id)])
                if open_po:
                    ref = ", ".join(open_po.mapped('name'))
                    raise UserError("The product %s could not be archived because of an open Purchase Order (%s)" % (product.display_name, ref))

                open_mo = self.env['mrp.production'].sudo().search([('state', 'not in', ['done', 'cancel']), ('product_id', '=', product.id)])
                if open_mo:
                    ref = ", ".join(open_mo.mapped('name'))
                    raise UserError("The product %s could not be archived because of an open Manufacturing Order (%s)" % (product.display_name, ref))

            self.mapped('orderpoint_ids').write({'active': False})
            self.env['mrp.bom'].sudo().search([('product_id', 'in', self.ids)]).write({'active': False})

        return super(ProductProduct, self).write(vals)

    def unlink(self):
        self.env['mrp.bom'].sudo().search([('product_id', 'in', self.ids)]).write({'active': False})
        return super(ProductProduct, self).unlink()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
