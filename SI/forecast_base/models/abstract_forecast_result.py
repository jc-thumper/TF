# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AbstractForecastResult(models.AbstractModel):
    _name = "abstract.forecast.result"
    _inherit = "abstract.period.info"
    _description = "Abstract Forecasting Result"

    _label_json = 'algorithm'
    _column_algo = 'algo'

    ###############################
    # FIELDS
    ###############################
    algo = fields.Char(string='Algorithm used to do the forecasting', default="")

    ###############################
    # HELPER FUNCTIONS
    ###############################
    @classmethod
    def get_required_fields(cls, forecast_level=None):
        parent_required_fields = super(AbstractForecastResult, cls).get_required_fields(forecast_level)

        required_fields_for_data = [
            (cls._label_json, str, None)
        ]
        return required_fields_for_data + parent_required_fields

    @classmethod
    def get_insert_fields(cls, forecast_level=None):
        parent_insert_fields = super(AbstractForecastResult, cls).get_insert_fields(forecast_level)

        insert_fields = [
            'algo'
        ]

        return parent_insert_fields + insert_fields

    @classmethod
    def _parse_json_fields_to_column_name(cls, fore_data):
        """

        :param fore_data:
        :return:
        """
        for item in fore_data:
            item[cls._column_algo] = item.pop(cls._label_json)

        return fore_data
