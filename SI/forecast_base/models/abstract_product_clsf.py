# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
from odoo.addons.si_core.utils import request_utils, string_utils

_logger = logging.getLogger(__name__)


class AbstractProductClassification(models.AbstractModel):
    _name = "abstract.product.classification"
    _description = "Product Classification Abstract"

    _label_json = None
    _column_clsf_id = None
    _column_pub_time = None

    ###############################
    # CONSTANTS
    ###############################
    CLSF_NAME = []

    ###############################
    # FIELDS
    ###############################
    name = fields.Selection([], required=True)

    ###############################
    # STANDARD FUNCTIONS
    ###############################
    def name_get(self):
        res = []
        name_dict = dict(self.CLSF_NAME)
        for clsf_name in self:
            name = clsf_name.name
            res.append((clsf_name.id, name_dict.get(name, '')))
        return res

    ###############################
    # PUBLIC METHODS
    ###############################
    def get_clsf_ids(self):
        """ Get all records in table

        :return: a dictionary of demand classification code and corresponding
        forecast group id.
        :rtype: dict
        {
            <demand_type: string>: <record_id: int>,
            <demand_type: string>: <record_id: int>,
            ...
        }
        """
        result = {}
        for record in self.search([]):
            result[record.name] = record.id

        return result

    ###############################
    # HELPER METHODS
    ###############################
    def update_product_cslf_type(self, data):
        """

        :param data:
        :return:
        """
        try:
            query_data = self._transform_demand_clsf_request(data)

            self._load_demand_clsf_request(query_data)

            logging.info("Update successfully %d record(s) to table %s in the table product_product." %
                         (len(query_data), self._name), extra={})

        except Exception as e:
            _logger.exception("An exception occur in update_product_cslf_type", exc_info=True)
            raise e

    def _transform_demand_clsf_request(self, json_data):
        """ Function transform json request to data import

        :param json_data:
        :return:
        :rtype: list(dict)
        """
        records = json_data.get('data', [])

        # map demand classification name to id
        demand_clf_records = self.sudo().get_clsf_ids()
        query_data = [
            {
                'pid': record.get('product_id', None),
                'clsf_id': demand_clf_records.get(record.get(self._label_json, None)),
                'pub_time': record.get('pub_time', None)}
            for record in records]
        return query_data

    def _load_demand_clsf_request(self, query_data):
        """

        :param query_data:
        :type query_data: list(dict)
        :return:
        """
        try:
            sql_query_template = """
                                    UPDATE product_product 
                                    SET {column_clsf_id} = %(clsf_id)s , {column_pub_time} = %(pub_time)s
                                    WHERE id = %(pid)s;
                                """ \
                .format(column_clsf_id=self._column_clsf_id,
                        column_pub_time=self._column_pub_time)

            self.env.cr.executemany(sql_query_template, query_data)

        except Exception as e:
            _logger.exception("An exception occur in _load_demand_clsf_request", exc_info=True)
            raise e

    def check_format_json_request(self, json_data):
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
                required_fields_for_data = [
                    ('product_id', int, None),
                    ('pub_time', str, request_utils.ExtraFieldType.DATETIME_FIELD_TYPE)
                ] + self.get_data_fields()
                is_valid_format = request_utils.check_format_data_array(list_data, required_fields_for_data)

            return is_valid_format

        except Exception as e:
            _logger.exception("An exception occur in check_format_json_request", exc_info=True)
            raise e
