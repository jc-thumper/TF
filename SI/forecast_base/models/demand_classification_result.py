# -*- coding: utf-8 -*-

import logging
import psycopg2

from odoo import models, fields, api
from odoo.addons.si_core.utils.string_utils import get_table_name
from odoo.addons.si_core.utils.database_utils import get_db_cur_time, append_log_access_fields_to_data
from odoo.addons.si_core.utils.request_utils import get_key_value_in_dict

from ..utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB, ALLOW_TRIGGER_QUEUE_JOB

from psycopg2 import IntegrityError
from time import time

_logger = logging.getLogger(__name__)


class DemandClassificationResult(models.Model):
    _name = "demand.classification.result"
    _inherit = 'abstract.public.info'
    _description = "Demand Classification Result"

    # map field in body request with the column name in the database
    _label_json = 'demand_type'
    _column_clsf_id = 'demand_clsf_id'
    _column_pub_time = 'pub_time'

    ###############################
    # FIELDS
    ###############################
    demand_clsf_id = fields.Many2one('demand.classification', required=True, ondelete='cascade', string='Demand Classification')
    has_approved = fields.Boolean(default=False, readonly=True)
    actual_dc_id = fields.Many2one('demand.classification', required=False, ondelete='cascade', default=None)

    ###############################
    # GENERAL FUNCTIONS
    ###############################
    @classmethod
    def get_data_fields(cls):
        return [
            (cls._label_json, str, None),
        ]

    def get_transformed_prod_info_req(self, json_data):
        """ Return transformed product information from json request

        :param json_data:
        :return:
        """
        return self._transform_product_info_request(json_data=json_data)

    def check_status_of_update_demand_classification_result(self, data_info):
        """
            Check demand classification result is updated in the Odoo database or not
        :param data_info: info to check
        :type data_info: a list of dict
        Each element have a format bellow
        {
            "demand_clsf_pub_time": a datetime str,
            "demand_clsf_records": int,
            "company_id": int
        }
        :return: status of each company and the flag with the value is True/False to countinue or not
        :rtype: (a list of dict, bool)
        [
            {
                "company_id": 1,
                "status": true
            },
            ...
        ]
        """
        result = []
        try:
            for item in data_info:
                company_id = item.get('company_id')
                expected_n_records = item.get('demand_clsf_records')
                pub_item = item.get('demand_clsf_pub_time')

                sql_query = """
                    SELECT count(*) as total_row
                    FROM demand_classification_result
                    WHERE pub_time = %s AND company_id = %s;
                """
                sql_param = (pub_item, company_id)

                self.env.cr.execute(sql_query, sql_param)
                records = self.env.cr.dictfetchall()
                actual_n_records = records[0].get('total_row', 0) if records else 0
                result.append({
                    "company_id": company_id,
                    "status": actual_n_records == expected_n_records
                })

            # if all status of company is False, we will stop at this step.
            is_continue = any([item.get('status') for item in result])

        except Exception:
            _logger.exception("An exception in check_status_of_update_demand_classificaton_result.", exc_info=True)
            raise
        return result, is_continue or False

    ###############################
    # API FUNCTIONS
    ###############################
    def get_json_required_fields(self, forecast_level, **kwargs):
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        # get required fields from forecast level
        required_fields_from_forecast_level = forecast_level_obj.get_required_fields()
        required_fields_of_models = [
            ("demand_type", str, None)
        ]
        return required_fields_from_forecast_level + required_fields_of_models

    def transform_json_data_request(self, list_data, **kwargs):
        demand_clsf_ids = self.env['demand.classification'].sudo().get_clsf_ids()
        instantly_update = self.env['forecasting.config.settings'].sudo().check_instantly_update()
        cur_time = get_db_cur_time(self.env.cr)
        for datum in list_data:
            datum = append_log_access_fields_to_data(self, datum, current_time=cur_time)
            demand_type = datum.pop("demand_type", None)
            datum.update({
                'demand_clsf_id': demand_clsf_ids.get(demand_type),
                'has_approved': instantly_update
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
            conflict_fields = forecast_level_obj.get_conflict_fields_for_demand_classification_result()
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
            _logger.info(sql_query)
            _logger.info(sql_params)
            self.env.cr.executemany(sql_query, sql_params)
            _logger.info("Insert/update %s rows into the model.", len(vals))

        except IntegrityError:
            logging.exception("Duplicate key in the table %s: %s", converted_table_name, vals, exc_info=True)
            raise
        except Exception:
            _logger.exception("Error in the function create_or_update_records.", exc_info=True)
            raise

    def trigger_next_actions(self, created_date, **kwargs):
        forecast_level = kwargs.get('forecast_level')
        self.update_demand_type_in_product_classification_info(created_date=created_date,
                                                               **{'forecast_level': forecast_level})

    def update_demand_type_in_product_classification_info(self, created_date, **kwargs):
        forecast_level = kwargs.get('forecast_level')
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        # trigger the event to update the product information in the table ``product.classification.info``
        product_clsf_info_obj = self.env['product.classification.info'].sudo()

        # get new updated records through API
        new_records = forecast_level_obj.get_latest_records_dict_for_demand_classification_result(
            obj=self, model=self.env[self._name], created_date=created_date)
        number_of_record = len(new_records)

        from odoo.tools import config
        threshold_trigger_queue_job = int(config.get("threshold_to_trigger_queue_job",
                                                     DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
        allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                             ALLOW_TRIGGER_QUEUE_JOB)

        if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
            product_clsf_info_obj.sudo().with_delay(max_retries=12) \
                .update_product_classification_infos(
                json_data=new_records, recomputed_fields=['demand_clsf_id'],
                source_table='demand_classification_result',
                **{
                    'forecast_level': forecast_level,
                    'created_date': created_date,
                    'update_active': True
                }
            )
        else:
            product_clsf_info_obj.sudo().update_product_classification_infos(
                json_data=new_records, recomputed_fields=['demand_clsf_id'],
                source_table='demand_classification_result',
                **{
                    'forecast_level': forecast_level,
                    'created_date': created_date,
                    'update_active': True
                }
            )

    ###############################
    # MODEL FUNCTIONS
    ###############################

    def get_latest_records_dict(self, created_date):
        """
        Get record_id of latest record from reordering.rules.with.forecast.tracker model
        :return:
        :rtype: list[dict
        """
        data_dict = []
        try:
            sql_query = """
                select
                    product_id, company_id, warehouse_id, demand_clsf_id, pub_time as demand_clsf_pub_time
                from demand_classification_result
                where create_date = %s;
           """
            sql_param = (created_date,)
            self.env.cr.execute(sql_query, sql_param)
            data_dict = self.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("Error in the function get_latest_records.", exc_info=True)
            raise e
        return data_dict

    ###############################
    # INITIAL FUNCTIONS
    ###############################

    @api.model
    def _create_demand_clsf_result_indices(self):
        """
        Create indices in the table
        :return:
        """
        try:
            sql_query = """
                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_idx_demand_clsf_result
                ON demand_classification_result (product_id, pub_time)
                WHERE company_id is NULL AND warehouse_id is NULL AND lot_stock_id is NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_idx_demand_clsf_result
                ON demand_classification_result (product_id, company_id, pub_time)
                WHERE warehouse_id is NULL AND lot_stock_id is NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_warehouse_idx_demand_clsf_result
                ON demand_classification_result (product_id, company_id, warehouse_id, pub_time);

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_warehouse_lot_stock_idx_demand_clsf_result
                ON demand_classification_result (product_id, company_id, warehouse_id, lot_stock_id, pub_time);
                
                CREATE UNIQUE INDEX IF NOT EXISTS demand_classification_result_product_id_company_id_warehouse_id
                ON demand_classification_result (product_id, company_id, warehouse_id, lot_stock_id, pub_time);                
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
