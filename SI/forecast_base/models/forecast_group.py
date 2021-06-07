# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime

import requests

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from odoo.addons.si_core.utils.database_utils import query
from odoo.addons.si_core.utils.string_utils import PeriodType


_logger = logging.getLogger(__name__)


class ForecastGroup(models.Model):
    _name = "forecast.group"
    _description = "Forecasting Group"

    ###############################
    # CONSTANTS
    ###############################
    CLSF_NAME = [
        ('group_a', 'Group A'),
        ('group_b', 'Group B'),
        ('group_c', 'Group C'),
        ('group_d', 'Group D'),
        ('group_e', 'Group E'),
        ('not_enough_data', 'Undefined')
    ]

    ###############################
    # FIELDS
    ###############################
    name = fields.Char(string="Name")
    reference_name = fields.Char(compute='_compute_reference_name', string='Reference Name')
    demand_clsf_id = fields.Many2one('demand.classification', string='Demand Classification',
                                     ondelete='cascade', required=True)

    period_type = fields.Selection(PeriodType.LIST_PERIODS)
    no_periods = fields.Integer(help='The number of forecast period ahead')
    frequency = fields.Selection(PeriodType.ORDERED_FORECASTING_FREQUENCY)

    client_available = fields.Boolean(compute='_compute_client_available',
                                      search='_search_client_available', default=False)

    ###############################
    # ONCHANGE FUNCTIONS
    ###############################
    @api.onchange('frequency', 'period_type')
    def _onchange_frequency(self):
        self.ensure_one()
        self._check_frequency_value()

    ###############################
    # COMPUTE FUNCTIONS
    ###############################
    def _compute_client_available(self):
        client_available = self.env['forecasting.config.settings'].check_client_available()
        for product in self:
            product.client_available = client_available

    @api.depends()
    def _compute_reference_name(self):
        name_map = dict(self.CLSF_NAME)
        for group in self:
            group.reference_name = name_map.get(group.name, 'Undefined')

    ###############################
    # SEARCH FUNCTIONS
    ###############################
    def _search_client_available(self, operator, value):
        if operator not in ('=', '!='):
            raise ValueError('Invalid operator: %s' % (operator,))
        if not isinstance(value, bool):
            raise ValueError('Invalid value type: %s' % (value,))
        client_available = self.env['forecasting.config.settings'].check_client_available()
        if value ^ client_available:
            domain = [('id', '=', '-1')]
        else:
            domain = []
        return domain

    ###############################
    # GENERAL FUNCTIONS
    ###############################
    @api.model
    def create(self, vals):
        self._check_frequency_value()

        res = super(ForecastGroup, self).create(vals)
        return res

    def write(self, vals):
        self._check_frequency_value()
        res = super(ForecastGroup, self).write(vals)

        return res

    ###############################
    # PUBLIC FUNCTIONS
    ###############################

    def name_get(self):
        """ name_get() -> [(id, name), ...]

        Returns a textual representation for the records in ``self``.
        By default this is the value of the ``display_name`` field.

        :return: list of pairs ``(id, text_repr)`` for each records
        :rtype: list(tuple)
        """
        result = [(False, 'Not Enough Data')]
        name = dict(self.CLSF_NAME)
        for record in self:
            result.append((record.id, name.get(record.name)))

        return result

    def get_forecast_group_records(self, domain, order_by, limit):
        """
        Get information of forecast group
        """
        selected_fields = ['name', 'period_type', 'no_periods', 'frequency', 'demand_clsf_id',
                           'create_date', 'write_date']

        forecast_groups = query(cr=self.env.cr,
                                table_name=self._name,
                                selected_fields=','.join(selected_fields),
                                domain=domain,
                                order_by=order_by,
                                limit=limit)

        demand_clsf_dict = dict(self.env['demand.classification'].search([]).mapped(lambda c: (c.id, c.name)))
        for group in forecast_groups:
            group['demand_clsf_id'] = demand_clsf_dict.get(group['demand_clsf_id'])

        return forecast_groups

    ###############################
    # PRIVATE FUNCTIONS
    ###############################
    def _check_frequency_value(self):
        for group in self:
            max_idx = PeriodType.FORECASTING_FREQUENCY_RANK.get(group.period_type, 1)
            current_idx = PeriodType.FORECASTING_FREQUENCY_RANK.get(group.frequency)
            if max_idx and current_idx and current_idx > max_idx:
                allow_frequency = list(map(lambda l: l[0],
                                           filter(lambda l: l[1] <= max_idx,
                                                  list(PeriodType.FORECASTING_FREQUENCY_RANK.items()))))
                raise ValidationError(_('The value for the field Forecasting Frequency should be %s.')
                                      % ', '.join(allow_frequency))

    def _update_clsf_fore_config_to_fe(self):
        auth_content = self.sudo().env['forecasting.config.settings'].get_auth_content()
        if auth_content:
            request_info = auth_content
            config_info = []
            for config in self:
                config_info.append({
                    'forecast_group': config.name,
                    'period_type': config.period_type,
                    'no_periods': config.no_periods,
                    'frequency': config.frequency,
                    'created_at': datetime.strftime(config.create_date, DEFAULT_SERVER_DATE_FORMAT),
                    'updated_at': datetime.strftime(config.write_date, DEFAULT_SERVER_DATE_FORMAT)
                })
            if config_info:
                request_info.update({'data': config_info})
                self._post_prod_fore_config(request_info)

    @staticmethod
    def _post_prod_fore_config(post_body):
        from ..utils.request_utils import ServerAPIv1, ServerAPICode
        direct_order_url = ServerAPIv1.get_api_url(ServerAPICode.UPDATE_CLSF_CONF)

        _logger.info('Call API to update classification forecasting configuration to FE service')
        headers = {
            'Content-type': 'application/json',
            # 'Accept': 'text/plain'
        }
        return requests.post(direct_order_url, data=json.dumps(post_body),
                             headers=headers, timeout=60)
