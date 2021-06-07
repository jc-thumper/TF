from odoo import api, fields, models, _

import logging
_logger = logging.getLogger(__name__)


class MrpProductionScheduleInherit(models.Model):
    _inherit = 'mrp.production.schedule'

    @api.model
    def open_table(self):
        tree_view = self.env.ref('tf_mrp_mps.import_export_mps_tree')
        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'views': [(tree_view.id, 'list')],
            'name': _('Master Production Schedule'),
            'res_model': 'mrp.production.schedule',
        }
        return action
