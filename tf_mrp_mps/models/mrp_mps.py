from odoo import api, fields, models, _

import logging
_logger = logging.getLogger(__name__)


class MrpProductionScheduleInherit(models.Model):
    _inherit = 'mrp.production.schedule'

    future_forecast_ids = fields.Many2many('mrp.product.forecast', string='Forecasted quantity at date using Export', compute='_compute_future_forecast_ids')

    def _compute_future_forecast_ids(self):
        for record in self:
            record.future_forecast_ids = [(6, 0, record.forecast_ids.filtered(lambda f: f.date > fields.Date.today()).ids)]

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
        ProductForecast  = self.env['mrp.product.forecast']
        for production_schedule in res:
            production_schedule_id = production_schedule['id']
            future_forecasts = self.env['mrp.production.schedule'].browse(production_schedule_id).forecast_ids.filtered(lambda f: f.date > fields.Date.today())
            dates = [f.date for f in future_forecasts]
            forecast_values_list = production_schedule['forecast_ids']
            for forecast_vals in forecast_values_list:
                if forecast_vals['date_stop'] not in dates:
                    ProductForecast .create({
                        'forecast_qty': 0,
                        'date': forecast_vals['date_stop'],
                        'replenish_qty': 0,
                        'production_schedule_id': production_schedule_id,
                    })
        return res
