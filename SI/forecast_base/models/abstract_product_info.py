# -*- coding: utf-8 -*-

import logging
import math
import numpy as np

from datetime import datetime
from time import sleep

from odoo import models, fields, api, _
from odoo.models import LOG_ACCESS_COLUMNS

from psycopg2.extensions import AsIs

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.addons.si_core.utils import request_utils, database_utils

_logger = logging.getLogger(__name__ )


class AbstractProductInfo(models.AbstractModel):
    _name = "abstract.product.info"
    _description = "Abstract Product Info"

    ###############################
    # FIELDS
    ###############################
    product_id = fields.Many2one('product.product', required=False, ondelete='cascade', string="Product")
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade', string='Company',
                                 default=lambda self: self.env.user.company_id.id)
    warehouse_id = fields.Many2one('stock.warehouse', required=False, ondelete='cascade')
    lot_stock_id = fields.Many2one('stock.location', required=False, ondelete='cascade')

    ###############################
    # GENERAL FUNCTIONS
    ###############################
    def create_mul_rows(self, vals_list, constrain_cols=None, get_lines=False, conflict_work=None):
        """

        :param conflict_work:
        :param get_lines:
        :param constrain_cols:
        :param vals_list:
        :type vals_list: list(dict)
        :return:
        """
        rows = self._create_multiple_rows(self._name, vals_list,
                                          constrain_cols=constrain_cols, conflict_work=conflict_work)

        if get_lines:
            return rows

    ###############################
    # HELPER FUNCTIONS
    ###############################

    @classmethod
    def get_required_fields(cls, forecast_level=None):
        # Default required fields for data
        required_fields_for_data = [
            ('product_id', int, None),
            ('company_id', int, None),
            ('warehouse_id', int, None),
            ('lot_stock_id', int, None)
        ]

        forecast_level = forecast_level or forecast_level.search([('name', '=', 'warehouse')])
        if forecast_level:
            obj = forecast_level.get_object()

            if obj:
                required_fields_for_data = obj.get_required_fields()

        return required_fields_for_data

    @classmethod
    def get_insert_fields(cls, forecast_level=None):

        # Default insert field
        insert_fields = ['product_id', 'company_id', 'warehouse_id']

        forecast_level = forecast_level or forecast_level.search([('name', '=', 'warehouse')])
        if forecast_level:
            obj = forecast_level.get_object()

            if obj:
                insert_fields = forecast_level.get_list_of_unique_keys()

        insert_fields += LOG_ACCESS_COLUMNS

        return insert_fields

    def get_product_info(self, product_id, company_id, warehouse_id,
                         lot_stock_id=None, limit=1):
        """ Function return the corresponding product info with
        entered parameters

        :param product_id:
        :param company_id:
        :param warehouse_id:
        :param lot_stock_id:
        :param limit:
        :return:
        """
        return self.search([
            ('product_id', '=', product_id),
            ('company_id', '=', company_id),
            ('warehouse_id', '=', warehouse_id),
            ('lot_stock_id', '=', lot_stock_id)
        ], limit=limit)

    def check_format_json_request(self, json_data):
        """
        Check format of the body of HTTP request in API
        :param json_data: dict object
        :return: True if valid, otherwise raise Error
        """
        try:
            is_valid_format = request_utils.check_json_fields(
                json_data,
                infos_required_field=[('server_pass', str, None),
                                      ('data', list, None)],
                infos_non_required_field=[])

            if is_valid_format:
                # check the format of ``data`` fields
                list_data = json_data.get('data', [])
                company_ids = np.unique([item.get('company_id') for item in list_data]).tolist()

                # get forecast level of all company
                forecast_level_dict = self.env['res.company'].get_forecast_level_by_company_id(company_ids=company_ids)

                result = {}
                for company_id in company_ids:
                    forecast_level_id = forecast_level_dict.get(company_id, None)
                    # filter records for this company
                    filtered_data = list(filter(lambda r: r.get('company_id') == company_id, list_data))

                    required_fields_for_data = self.get_required_fields(forecast_level=forecast_level_id)

                    is_valid_format = self._check_format_data_field(filtered_data, required_fields_for_data)
                    result[company_id] = is_valid_format

                is_valid_format = all(result.values())

        except Exception as e:
            _logger.exception("An exception occur in check_format_json_request", exc_info=True)
            raise e

        return is_valid_format

    @staticmethod
    def _check_format_data_field(data_field, required_fields_for_data):
        """
        Check format of the card data in body of HTTP request in API update
        classification

        :param data_field: list dicts
        :return: True if valid, otherwise raise Error
        """
        try:
            is_valid_format = True
            idx = 0
            size_data = len(data_field)
            while is_valid_format and idx < size_data:
                ith_item = data_field[idx]
                is_valid_format = request_utils.check_json_fields(
                    ith_item,
                    infos_required_field=required_fields_for_data,
                    infos_non_required_field=[])
                idx += 1

        except Exception as e:
            _logger.exception("An exception occur in _check_format_data_field", exc_info=True)
            raise e

        return is_valid_format

    def _append_log_update_data(self, updated_fields, query_param):
        updated_fields += ['write_uid', 'write_date']
        cur_time = database_utils.get_db_cur_time(self.env.cr)
        for log in LOG_ACCESS_COLUMNS:
            if log == 'write_uid':
                query_param.append(self.env.ref("base.partner_root").id)
            elif log == 'write_date':
                query_param.append(cur_time)

    def _append_log_create_data(self, inserted_fields, query_params):
        inserted_fields += LOG_ACCESS_COLUMNS
        for param in query_params:
            self._append_log_create_datum(inserted_fields, param)

    def _append_log_create_datum(self, inserted_fields, param):
        inserted_fields += LOG_ACCESS_COLUMNS
        cur_time = database_utils.get_db_cur_time(self.env.cr).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        for log in LOG_ACCESS_COLUMNS:
            if log == 'create_uid':
                param.append(self.env.ref("base.partner_root").id)
            elif log == 'create_date':
                param.append(cur_time)
            elif log == 'write_uid':
                param.append(self.env.ref("base.partner_root").id)
            elif log == 'write_date':
                param.append(cur_time)

    def _create_multiple_rows(self, model_name, dict_data, chunk_size=200,
                              constrain_cols=None, effected_cols=None,
                              conflict_work=None):
        """
        Function create new rows, which have been not existed before, of
        table model_name

        :param dict_data: list of dict have same structure, which are used to
        create new record have been not existed before.
        :type dict_data: list(dict)
        :return: list of objects have just created
        :rtype: recordset
        """
        items = self.env[model_name]
        if dict_data:
            dict_data = self._filter_dict_data(dict_data, constrain_cols)
            cur_time = database_utils.get_db_cur_time(self.env.cr)
            dict_data = self._extend_data_with_log_info(dict_data, cur_time)
            if not conflict_work:
                conflict_work = """UPDATE SET (write_date) = (now() at time zone 'UTC')""" \
                    if self._log_access \
                    else """NOTHING"""
            time_to_fail = 5

            rowf = '(' + ','.join(['%s'] * len(dict_data[0].keys())) + ')'
            cols_name = ','.join(list(dict_data[0].keys()))
            table_name = model_name.replace('.', '_')

            index = 0
            chunks = math.ceil(len(dict_data) / chunk_size)
            latest_updated_records_list = list(dict_data)

            count_fail = 0

            constrain_cols = (constrain_cols or [])
            constrain_cols_str = ','.join(constrain_cols)
            effected_cols = effected_cols or []
            while index < chunks:
                index += 1
                try:
                    upper_bound = chunk_size * index if index < chunks else len(dict_data)
                    sub_records = latest_updated_records_list[chunk_size * (index - 1): upper_bound]
                    query = """
                                    INSERT INTO {table_name} ({cols_name})
                                    VALUES {rows}
                                    ON CONFLICT ({constrain_cols_str})
                                    DO %s;
                               """.format(
                        table_name=table_name,
                        rows=", ".join([rowf] * len(sub_records)),
                        constrain_cols_str=constrain_cols_str,
                        cols_name=cols_name
                    )
                    dict_test = {}
                    for row in sub_records:
                        a = dict_test.setdefault((row['product_id'], row['company_id'], row['warehouse_id'],
                                                  row['start_date'], row['period_type']), 0)
                        dict_test[(row['product_id'], row['company_id'], row['warehouse_id'],
                                   row['start_date'], row['period_type'])] = a+1
                    record_data = [arg
                                   for row in sub_records
                                   for arg in row.values()] + [AsIs(conflict_work)]

                    try:
                        self.env.cr.execute(query, record_data)
                        self.env.cr.commit()
                    except Exception as e:
                        _logger.error("Failed to insert %s: %s" %
                                      (table_name, e))
                        raise

                    items = self.env[model_name].search([('write_date', '=', cur_time)])
                    # Step: recompute computed fields
                    if effected_cols:
                        items.modified(effected_cols)

                    count_fail = 0

                except Exception as e:
                    _logger.exception(e)
                    sleep(10.0)
                    index -= 1
                    count_fail += 1
                    if count_fail == time_to_fail:
                        _logger.exception(_("Create rows in table %s is Fail", table_name))
        return items

    def _extend_data_with_log_info(self, dict_data, cur_time=None):
        """

        :param dict_data:
        :type dict_data:
        :param cur_time: the time create or update the record
        :type cur_time: datetime
        :return:
        """
        if self._log_access:
            if not cur_time:
                cur_time = database_utils.get_db_cur_time(self.env.cr)

            dict_data = [{
                **dict_datum,
                **{
                    'create_uid': self.env.ref('base.partner_root').id,
                    'create_date': cur_time,
                    'write_uid': self.env.ref('base.partner_root').id,
                    'write_date': cur_time
                }
            } for dict_datum in dict_data]
        return dict_data

    @staticmethod
    def _filter_dict_data(dict_data, constrain_cols):
        """ Function remove duplicate and choose latest data

        :param dict_data:
        :param constrain_cols:
        :return: The filtered list
        :rtype: list(dict)
        """
        try:
            filtered_dict_data = {}
            for data in dict_data:
                key = tuple(map(lambda col_name: data.get(col_name), constrain_cols))
                record_data = filtered_dict_data.setdefault(key, data)
                if data.get('write_date'):
                    if record_data['write_date'] < data['write_date']:
                        filtered_dict_data[key] = data
            dict_data = list(filtered_dict_data.values())

        except Exception as e:
            _logger.exception("Having some error when filter data "
                              "base on constrain columns: %s" % e)
        return dict_data
