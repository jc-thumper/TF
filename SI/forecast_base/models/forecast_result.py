# -*- coding: utf-8 -*-

import logging
import psycopg2

from odoo import models, fields, api
from odoo.addons import decimal_precision as dp
from odoo.addons.si_core.utils.request_utils import ExtraFieldType, get_key_value_in_dict
from odoo.addons.si_core.utils.string_utils import get_table_name
from odoo.addons.si_core.utils.database_utils import get_db_cur_time, append_log_access_fields_to_data
from odoo.exceptions import UserError

from time import time
from psycopg2.extensions import AsIs
from psycopg2 import IntegrityError

_logger = logging.getLogger(__name__)


class ForecastResult(models.Model):
    _name = "forecast.result"
    _inherit = 'abstract.forecast.result'
    _description = "Forecasting Result"
    _order = "pub_time desc"

    ###############################
    # FIELDS
    ###############################
    forecast_result = fields.Float(required=False,
                                   digits=dp.get_precision('Product Unit of Measure'))
    upper_1 = fields.Float(required=False)
    upper_2 = fields.Float(required=False)
    lower_1 = fields.Float(required=False)
    lower_2 = fields.Float(required=False)

    ###############################
    # API FUNCTIONS
    ###############################
    def get_json_required_fields(self, forecast_level, **kwargs):
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        # get required fields from forecast level
        required_fields_from_forecast_level = forecast_level_obj.get_required_fields()
        required_fields_of_models = [
            ('algorithm', str, None),
            ('period_type', str, None),
            ('pub_time', str, ExtraFieldType.DATETIME_FIELD_TYPE),
            ('start_date', str, ExtraFieldType.DATE_FIELD_TYPE),
            ('end_date', str, ExtraFieldType.DATE_FIELD_TYPE),
            ('forecast_result', float, None),
            ('upper_1', float, None),
            ('upper_2', float, None),
            ('lower_1', float, None),
            ('lower_2', float, None)
        ]
        return required_fields_from_forecast_level + required_fields_of_models

    def transform_json_data_request(self, list_data, **kwargs):
        """

        :param list_data: the list of dictionaries that store forecast results sent from engine
        :type list_data: list[dict]
        :param kwargs:
        :return:
        :rtype: list[dict]
        """
        for datum in list_data:
            datum = append_log_access_fields_to_data(self, datum)
            datum.update({
                'algo': datum.pop('algorithm')
            })
        return list_data

    def create_or_update_records(self, vals, forecast_level, **kwargs):
        converted_table_name = get_table_name(self._name)
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        try:
            # Run SQL code to update new data into the table
            # get insert fields from the data
            inserted_fields = list(vals[0].keys())

            # get conflict fields from forecast level
            conflict_fields = forecast_level_obj.get_conflict_fields_for_forecast_result()
            updated_fields = list(set(inserted_fields) - set(conflict_fields))

            sql_query = """
                INSERT INTO %s (%s)
                VALUES (%s)
                ON CONFLICT (%s)
                DO UPDATE SET 
            """ % (converted_table_name,
                   ','.join(inserted_fields),
                   ','.join(["%s"] * len(inserted_fields)),
                   ','.join(conflict_fields))

            sql_query += ", ".join(["%s = EXCLUDED.%s" % (field, field) for field in updated_fields])
            sql_query += ";"

            sql_params = [get_key_value_in_dict(item, inserted_fields) for item in vals]
            self.env.cr.executemany(sql_query, sql_params)
            _logger.info("Insert/update %s rows into the model.", len(vals))

        except IntegrityError:
            logging.exception("Duplicate key in the table %s: %s", converted_table_name, vals, exc_info=True)
            raise
        except Exception:
            _logger.exception("Error in the function create_or_update_records.", exc_info=True)
            raise

    def trigger_next_actions(self, created_date, **kwargs):
        """

        :param created_date:
        :type created_date: str
        :param kwargs:
        :return:
        :rtype: None
        """
        forecast_level = kwargs.get('forecast_level')
        self.update_forecast_result_in_forecast_result_adjust_line(created_date=created_date,
                                                                   **{'forecast_level': forecast_level})

    def update_forecast_result_in_forecast_result_adjust_line(self, created_date, **kwargs):
        """ Function update the forecast result that have the created date is ``create_date``
        to the forecast_result_adjust_line table. we will push this task to queue job to do this
        automatically

        :param created_date:
        :type created_date: str
        :param kwargs:
        :return:
        """
        forecast_level = kwargs.get('forecast_level')
        if forecast_level:
            forecast_result_adjust_line_obj = self.env['forecast.result.adjust.line'].sudo()
            forecast_result_adjust_line_obj\
                .update_forecast_adjust_line_table(
                    created_date,
                    **{
                        'forecast_level': forecast_level
                    }
               )
        else:
            UserError('Miss the forecast_level for current company')

    ###############################
    # HELPER FUNCTIONS
    ###############################
    @staticmethod
    def get_selected_and_group_by_fields_to_check_client_available(self):
        """
        Get list of field name to query data in Forecast Result
        to check client is available or not
        :return: list of field name to query data in Forecast Result
        to check client is available or not
        :rtype: List[str]
        """
        result = ['product_id', 'company_id', 'warehouse_id', 'pub_time']
        return result

    def get_no_nearest_forecast_results(self):
        """
        Get number of records from latest publish time from the table Forecast Result
        :return: The number of nearest forecast results at specify pub_time
        :rtype: Tuple[int, Datetime]
        """
        try:
            sql_query = """
                SELECT COUNT(*), %s
                FROM forecast_result
                WHERE pub_time = (SELECT max(pub_time) FROM forecast_result)
                GROUP BY %s;        
                """
            selected_fields = self.get_selected_and_group_by_fields_to_check_client_available()
            selected_fields_str = AsIs(','.join(selected_fields))
            sql_param = (selected_fields_str, selected_fields_str,)
            self.env.cr.execute(sql_query, sql_param)
            records = self.env.cr.dictfetchall()
            n_records = len(records)
            pub_time = records[0].get('pub_time', None) if n_records else None
            _logger.info("Number records in forecast result at %s: %s", pub_time, n_records)
            return n_records, pub_time

        except Exception as e:
            _logger.exception("An exception in get_no_nearest_forecast_results", exc_info=True)
            raise e

    @api.model
    def create_virtual_fore_result(self, product_id, warehouse_id, company_id,
                                   period_type, start_date, end_date):
        """ Create a virtual record id

        :param period_type:
        :param end_date:
        :param start_date:
        :param product_id:
        :param warehouse_id:
        :param company_id:
        :param product_id:
        :return: id new record
        :rtype: int
        """
        rec_id = self.create({
            'product_id': product_id,
            'warehouse_id': warehouse_id,
            'company_id': company_id,
            'period_type': period_type,
            'start_date': start_date,
            'end_date': end_date,
        }).id

        return rec_id

    @classmethod
    def get_insert_fields(cls, forecast_level=None):
        parent_insert_fields = super(ForecastResult, cls).get_insert_fields(forecast_level)

        insert_fields = [
            'forecast_result',
            'upper_1',
            'upper_2',
            'lower_1',
            'lower_2',
        ]

        return parent_insert_fields + insert_fields

    def write_new_forecast_result(self, data_records):
        try:
            sql_query_template = """
                UPDATE forecast_result 
                SET                                         
                    algo = %(algorithm)s,
                    period_type = %(period_type)s,
                    pub_time = %(pub_time)s,
                    start_date = %(start_date)s,
                    end_date = %(end_date)s,
                    forecast_result = %(forecast_result)s,
                    upper_1 = %(upper_1)s,
                    upper_2 = %(upper_2)s,
                    lower_1 = %(lower_1)s,
                    lower_2 = %(lower_2)s                                      
                WHERE 
                    product_id = %(product_id)s AND
                    company_id = %(company_id)s AND 
                    warehouse_id = %(warehouse_id)s AND 
                    lot_stock_id = %(lot_stock_id)s;
            """

            self.env.cr.executemany(sql_query_template, data_records)
            _logger.info("Write %d record(s) in the table forecast_result."
                         % len(data_records), extra={})

        except Exception as e:
            _logger.exception("An exception occur in write_new_forecast_result", exc_info=True)
            raise e

    ###############################
    # INITIAL FUNCTIONS
    ###############################
    @api.model
    def _create_forecast_result_indices(self):
        """
        Create indices in the table
        :return:
        """
        try:
            sql_query = """
                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_idx_forecast_result
                ON forecast_result (product_id, pub_time, start_date, period_type)
                WHERE company_id is NULL AND warehouse_id is NULL AND lot_stock_id is NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_idx_forecast_result
                ON forecast_result (product_id, company_id, pub_time, start_date, period_type)
                WHERE warehouse_id is NULL AND lot_stock_id is NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_warehouse_idx_forecast_result
                ON forecast_result (product_id, company_id, warehouse_id, pub_time, start_date, period_type);

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_warehouse_lot_stock_idx_forecast_result
                ON forecast_result (product_id, company_id, warehouse_id, lot_stock_id, pub_time, start_date, period_type);                
            """
            t1 = time()
            self.env.cr.execute(sql_query)
            t2 = time()
            logging.info("Finish create indices in the table %s in %f (s)." % (self._name, t2 - t1))

        except psycopg2.DatabaseError as db_error:
            logging.exception("Error when creating index in the table %s.: %s" % (self._name, db_error),
                              exc_info=True)
            raise db_error

        except Exception as e:
            logging.exception("Another error occur when creating index in the table %s: %s" % (self._name, e),
                              exc_info=True)
            raise e
