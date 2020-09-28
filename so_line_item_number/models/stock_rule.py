# -*- coding: utf-8 -*-

from odoo import api, fields, models



class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values):
        move_values = super(StockRule, self)._get_stock_move_values(product_id, product_qty, product_uom, location_id, name, origin, company_id, values)
        move_values['origin'] = values.get('origin') or origin
        return move_values

    def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom):
        mo_values = super(StockRule, self)._prepare_mo_vals(product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom)
        mo_values['origin'] = values.get('origin') or origin
        return mo_values


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
