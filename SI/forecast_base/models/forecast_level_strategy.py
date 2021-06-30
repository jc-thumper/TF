# -*- coding: utf-8 -*-

import logging

from typing import Union

from odoo import models, fields, api, _
from ..utils.config_utils import ForecastLevelLogicConfig

_logger = logging.getLogger(__name__)


class ForecastLevelStrategy(models.Model):
    _name = "forecast.level.strategy"
    _description = "Forecast Level Strategy"

    ###############################
    # FIELDS
    ###############################
    name = fields.Selection(string='Forecast Level',
                            selection=ForecastLevelLogicConfig.FORECAST_LEVEL_LOGIC,
                            default=ForecastLevelLogicConfig.WAREHOUSE_LEVEL)

    unique_keys = fields.Text(string='Unique keys', help='Unique fields to process data for each level')
    description = fields.Text(string='Description', compute='_compute_description')
    has_warehouse_level = fields.Boolean(string='Has Warehouse Level', compute='_compute_has_warehouse_level')

    ###############################
    # COMPUTE FUNCTIONS
    ###############################
    def _compute_has_warehouse_level(self):
        for level in self:
            level.has_warehouse_level = self.get_has_warehouse_level()

    def _compute_description(self):
        for level in self:
            level.description = ForecastLevelLogicConfig.get_description(level.name)

    ###############################
    # HELPER FUNCTIONS
    ###############################
    def name_get(self):
        result = []
        for record in self:
            name = dict(self._fields['name'].selection).get(record.name)
            result.append((record.id, name))

        return result

    def get_has_warehouse_level(self):
        self.ensure_one()
        return 'warehouse_id' in self.unique_keys

    def get_product_field(self):
        self.ensure_one()
        product_field = None
        if self.name == ForecastLevelLogicConfig.WAREHOUSE_LEVEL:
            product_field = 'product_id'
        return product_field

    def get_list_of_unique_keys(self):
        """

        :return:
        :rtype: list[str]
        """
        self.ensure_one()
        return self.unique_keys.split(',')

    def get_list_of_extend_keys(self):
        """

        :return:
        :rtype: list[str]
        """
        self.ensure_one()
        unique_keys = self.get_list_of_unique_keys()
        return unique_keys

    @staticmethod
    def create_obj(self, forecast_level, **kwargs):
        obj = None
        return obj

    def get_object(self):
        """ Function return the Object containing the logic use when switch the forecast level;
        it will return ``None`` if this level don't exist before.

        :return:
        :rtype: Union[None, object]
        """
        self.ensure_one()
        obj = None
        return obj
