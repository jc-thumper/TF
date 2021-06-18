from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class StockMoveInherit(models.Model):
    _inherit = 'stock.move'

    bom_origin_id = fields.Char(string="Bill of Material Origin")


class MrpProductionInherit(models.Model):
    _inherit = 'mrp.production'

    def action_confirm(self):
        self._check_company()
        for production in self:
            if not production.move_raw_ids:
                raise UserError(_("Add some materials to consume before marking this MO as to do."))
            for move_raw in production.move_raw_ids:
                move_raw.write({
                    'unit_factor': move_raw.product_uom_qty / production.product_qty,
                })
            production._generate_finished_moves()

            if self.env.company.allow_grouping_bom:
                if not production.move_dest_ids:
                    bom_origin_id = production.bom_id.id
                else:
                    bom_origin_id = production.move_dest_ids.bom_origin_id
                production.move_raw_ids.write({'bom_origin_id': bom_origin_id})
                production.move_finished_ids.write({'bom_origin_id': bom_origin_id})

            production.move_raw_ids._adjust_procure_method()
            (production.move_raw_ids | production.move_finished_ids)._action_confirm()
        return True
