from odoo import api, fields, models, _

from odoo.tools.profiler import profile

import logging
_logger = logging.getLogger(__name__)


class MrpProductionScheduleInherit(models.Model):
    _inherit = 'mrp.production.schedule'

    future_forecast_ids = fields.One2many(
        'mrp.product.forecast',
        'production_schedule_id',
        string='Forecasted quantity at date using to Export',
        domain=lambda self: [('date', '>', fields.Date.today())]
    )

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

    @profile
    def get_production_schedule_view_state(self):
        res = super().get_production_schedule_view_state()
        ProductForecast = self.env['mrp.product.forecast']
        today = fields.Date.context_today(self)
        # TODO: to check if we can browse all the record for `mrp.production.schedule`
        # and filter for `forecast_ids` in the values list
        mrp_production_schedule_ids = [mps['id'] for mps in res]
        production_schedules = self.browse(mrp_production_schedule_ids)
        production_schedules.mapped('forecast_ids')
        production_schedule_vals = {e['id']: e['forecast_ids'] for e in res}

        vals_list = []
        for schedule in production_schedules:
            dates = schedule.forecast_ids.filtered(lambda x: x.date >= today).mapped('date')
            schedule_vals = list(filter(lambda p: p['date_stop'] not in dates, production_schedule_vals[schedule.id]))
            for forecast_vals in schedule_vals:
                vals_list.append({
                    'forecast_qty': 0,
                    'date': forecast_vals['date_stop'],
                    'production_schedule_id': schedule.id,
                })

        ProductForecast.create(vals_list)
        return res
