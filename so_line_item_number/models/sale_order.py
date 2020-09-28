# -*- coding: utf-8 -*-

from odoo import api, fields, models



class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.onchange('order_line')
    def _onchange_add_item_number(self):
        order_lines = self.order_line
        main_product_lines = order_lines.filtered(lambda line: not line.parent_product_id and not line.item_number)
        optional_product_lines = order_lines.filtered(lambda line: line.parent_product_id and not line.item_number)

        next_number = max(order_lines.mapped('item_number') or [0]) + 1
        for i, line in enumerate(main_product_lines, start=next_number):
            line.item_number = i

        for line in optional_product_lines:
            parent_lines = order_lines.filtered(lambda r: r.product_id == line.parent_product_id)
            item_number = max(parent_lines.mapped('item_number') or [0]) or next_number
            line.item_number = item_number


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    parent_product_id = fields.Many2one('product.product')
    item_number = fields.Integer(default=0)

    def _prepare_procurement_values(self, group_id=False):
        values = super(SaleOrderLine, self)._prepare_procurement_values(group_id)
        values['origin'] = "%s-%s" % (self.order_id.name, self.item_number)
        return values

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
