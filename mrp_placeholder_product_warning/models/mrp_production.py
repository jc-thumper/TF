# -*- encoding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_confirm(self):
        show_warning = self._context.get('show_placeholder_product_warning', False)

        orders_to_confirm = self.env['mrp.production']
        for order in self:
            if order.move_raw_ids.filtered(lambda r: 'Placeholder' in r.product_id.name or not r.product_id.active):
                if show_warning:
                    raise UserError("Please update the PLACEHOLDER/ARCV product before marking this MO as to do.")
            else:
                orders_to_confirm |= order

        return super(MrpProduction, orders_to_confirm).action_confirm()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
