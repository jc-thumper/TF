# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

MIN_NO_PAST_PERIOD = 6
MIN_NO_FUTURE_PERIOD = 6
MAX_NO_PAST_PERIOD = 24
MAX_NO_FUTURE_PERIOD = 24
NO_PAST_PERIOD = 24
NO_FUTURE_PERIOD = 6
NO_SAFETY_EXPIRE_DATE = 30


class ResConfigSettings(models.TransientModel):
    """
    This model add some fields in Settings menu in Inventory app
    """
    _inherit = 'res.config.settings'

    #################################
    # FIELDS
    #################################

    past_periods = fields.Integer("Past Periods", required=True, default=NO_PAST_PERIOD)
    future_periods = fields.Integer("Future Periods", required=True, default=NO_FUTURE_PERIOD)

    forecast_level_id = fields.Many2one('forecast.level.strategy',
                                        related='company_id.forecast_level_id',
                                        required=True,
                                        readonly=False)
    ########################################################
    # ONCHANGE FUNCTIONS
    ########################################################

    #################################
    # MODEL FUNCTIONS
    #################################
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(
            past_periods=int(get_param('forecasting.past_periods', NO_PAST_PERIOD)),
            future_periods=int(get_param('forecasting.future_periods', NO_FUTURE_PERIOD))
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param

        if self.check_condition_forecasting_setting():
            self._update_demand_chart()
            set_param('forecasting.past_periods',
                      self.past_periods)
            set_param('forecasting.future_periods',
                      self.future_periods)

    def check_condition_forecasting_setting(self):
        if self.past_periods < MIN_NO_PAST_PERIOD:
            raise ValidationError(_("The number of historical periods should greater than %s periods", MIN_NO_PAST_PERIOD))

        if self.future_periods < MIN_NO_FUTURE_PERIOD:
            raise ValidationError(_("The number of future periods should greater than %s periods", MIN_NO_FUTURE_PERIOD))

        if self.past_periods > MAX_NO_PAST_PERIOD:
            raise ValidationError(_("The number of historical periods should less than %s periods", MAX_NO_PAST_PERIOD))

        if self.future_periods > MAX_NO_FUTURE_PERIOD:
            raise ValidationError(_("The number of future periods should less than %s periods", MAX_NO_FUTURE_PERIOD))

        return True

    #################################
    # HELPER FUNCTIONS
    #################################
    def get_future_periods(self):
        return int(self.env['ir.config_parameter']
                   .sudo()
                   .get_param('forecasting.future_periods', NO_FUTURE_PERIOD))

    def get_past_periods(self):
        return int(self.env['ir.config_parameter']
                   .sudo()
                   .get_param('forecasting.past_periods', NO_PAST_PERIOD))

    @staticmethod
    def redirect_to_homepage(url='', target='new'):
        """
        Redirect to a new page with the URL
        :param url:
        :param target:
        :return:
        """
        default_page = 'https://omniborders-web.qa.novobi.com/smart-inventory'
        result = {
            "type": "ir.actions.act_url",
            "url": url or default_page,
            "target": target
        }
        return result

    #################################
    # PRIVATE FUNCTIONS
    #################################
    def _update_demand_chart(self):
        past_periods = self.get_past_periods()
        future_periods = self.get_future_periods()
        has_updated = False

        if self.past_periods != past_periods:
            # update number of past periods
            self.env['ir.config_parameter'].sudo() \
                .set_param('forecasting.past_periods', self.past_periods)
            fras = self.env['forecast.result.adjust'].search([])
            fras.update_adjust_line_ids()
            has_updated = True
            fras.recompute_actual_chart_data()

        if self.future_periods != future_periods:
            # update number of future periods
            self.env['ir.config_parameter'].sudo() \
                .set_param('forecasting.future_periods', self.future_periods)
            fras = self.env['forecast.result.adjust'].search([])
            if not has_updated:
                fras.update_adjust_line_ids()
            fras.recompute_forecast_chart_data()
