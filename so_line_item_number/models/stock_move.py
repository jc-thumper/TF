# -*- coding: utf-8 -*-

from odoo import api, fields, models



class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_procurement_values(self):
        values = super(StockMove, self)._prepare_procurement_values()
        values['origin'] = self.origin or self.group_id.name or self.picking_id.name or "/"
        return values


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
