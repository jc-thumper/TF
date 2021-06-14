from odoo import api, fields, models, _


class SyncRRToMPS(models.Model):
    _name = "sync.rr.mps"
    _description = 'Sync data from reodering rule to mps'

    def run_sync(self):
        lot_stock_ids = self.env['stock.warehouse'].search([]).mapped('lot_stock_id').ids
        reordering_rules = self.env['stock.warehouse.orderpoint'].search([('location_id', 'in', lot_stock_ids)])
        product_ids = reordering_rules.mapped('product_id').ids
        mp_schedules = self.env['mrp.production.schedule'].search([('product_id', 'in', product_ids)])

        for reordering_rule in reordering_rules:
            for mps in mp_schedules:
                if reordering_rule.product_id.id == mps.product_id.id:
                    mps.write({'forecast_target_qty': reordering_rule.safety_stock_target,
                               'min_to_replenish_qty': reordering_rule.product_min_qty,
                               'max_to_replenish_qty': reordering_rule.product_max_qty,
                               })
