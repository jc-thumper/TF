import datetime

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

    def get_production_schedule_view_state(self):
        res = super(MrpProductionScheduleInherit, self).get_production_schedule_view_state()
        Product_Forecast = self.env['mrp.product.forecast']
        for production_schedule in res:
            production_schedule_id = production_schedule.get('id')
            forecasts = self.env['mrp.production.schedule'].browse(production_schedule_id).forecast_ids.filtered(lambda f: f.date > datetime.datetime.today().date())
            dates = [f.date for f in forecasts]
            forecast_values = production_schedule.get('forecast_ids')
            for forecast in forecast_values:
                if forecast.get('date_stop') not in dates:
                    Product_Forecast.create({
                        'forecast_qty': 0,
                        'date': forecast.get('date_stop'),
                        'replenish_qty': 0,
                        'production_schedule_id': production_schedule_id,
                    })
        return res
