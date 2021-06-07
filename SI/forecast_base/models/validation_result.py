# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
from odoo.addons.si_core.utils import request_utils
from odoo.addons.si_core.utils.request_utils import ExtraFieldType

_logger = logging.getLogger(__name__)

class ValidationResult(models.Model):
    _name = "validation.result"
    _inherit = 'abstract.forecast.result'
    _description = "Validation Result"

    ###############################
    # FIELDS
    ###############################
    validation_result = fields.Float(required=True)

    ###############################
    # HELPER FUNCTIONS
    ###############################
    @classmethod
    def get_required_fields(cls, forecast_level=None):
        parent_required_fields = super(ValidationResult, cls).get_required_fields(forecast_level)

        required_fields_for_data = [
            ('validation_result', float, None),
        ]
        return required_fields_for_data + parent_required_fields

    @classmethod
    def get_insert_fields(cls, forecast_level=None):
        parent_insert_fields = super(ValidationResult, cls).get_insert_fields(forecast_level)

        insert_fields = [
            'validation_result'
        ]

        return parent_insert_fields + insert_fields

    def _transform_product_info_request(self, json_data, extra_fields=None):
        """
        Override function
        :param json_data:
        :return:
        :rtype: list(dict)
        """
        transformed_data = super()._transform_product_info_request(json_data)
        parsed_data = self._parse_json_fields_to_column_name(transformed_data)

        return parsed_data

    @classmethod
    def check_format_json_request(cls, json_data):
        """
        Check format of the body of HTTP request in API update product classification

        :param json_data: dict object
        :return: True if valid, otherwise raise Error
        """
        try:
            is_valid_format = request_utils.check_json_fields(
                json_data,
                infos_required_field=[('server_pass', str, None),
                                      ('data', list, None)],
                infos_non_required_field=[])

            # check the format of ``data`` fields
            list_data = json_data.get('data', [])
            if is_valid_format:
                required_fields_for_data = cls._get_json_required_fields()
                non_required_fields_for_data = []
                is_valid_format = request_utils.check_format_data_array(
                    list_data,
                    required_fields_for_data=required_fields_for_data,
                    infos_non_required_field=non_required_fields_for_data
                )
            return is_valid_format
        except Exception as e:
            _logger.exception("There was some problems when checking json\'s format.", exc_info=True)
            raise e

    @classmethod
    def _get_json_required_fields(cls):
        return [('product_id', int, None),
                ('company_id', int, None),
                ('warehouse_id', int, None),
                ('lot_stock_id', int, None),
                ('algorithm', str, None),
                ('period_type', str, None),
                ('pub_time', str, ExtraFieldType.DATETIME_FIELD_TYPE),
                ('start_date', str, ExtraFieldType.DATE_FIELD_TYPE),
                ('end_date', str, ExtraFieldType.DATE_FIELD_TYPE),
                ('validation_result', float, None)]
