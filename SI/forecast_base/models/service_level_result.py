# -*- coding: utf-8 -*-

import psycopg2
import logging

from odoo import models, fields, api
from odoo.addons.si_core.utils.string_utils import get_table_name
from odoo.addons.si_core.utils.database_utils import get_db_cur_time, append_log_access_fields_to_data
from odoo.addons.si_core.utils.request_utils import get_key_value_in_dict

from ..utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB

from psycopg2 import IntegrityError
from time import time

_logger = logging.getLogger(__name__)


class ServiceLevelResult(models.Model):
    _name = "service.level.result"
    _inherit = 'abstract.public.info'
    _description = "Service Level Result"

    # map field in body request with the column name in the database
    _label_json = 'service_level'
    _column_sl_id = 'service_level_id'
    _column_pub_time = 'pub_time'

    ###############################
    # FIELDS
    ###############################
    service_level_id = fields.Many2one('service.level', required=True, ondelete='cascade',
                                       help='The Result has been sent from engine')
    has_approved = fields.Boolean(default=False, readonly=True)
    actual_sl_id = fields.Many2one('service.level', required=False, ondelete='cascade',
                                   default=None, help='The Service Level that user is using')

    seq = fields.Integer(required=True, default=2**31-1)

    ###############################
    # MODEL FUNCTIONS
    ###############################
    def check_status_of_update_service_level_result(self, data_info):
        """
        Check service level result is updated in the Odoo database or not
        :param list[dict] data_info: info to check
        Ex: [
                {
                    "service_level_pub_time": a datetime str,
                    "service_level_records": int,
                    "company_id": int
                },
            ]
        :return: status of each company and the flag with the value is True/False to continue or not
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
        is_continue = False
        try:
            for item in data_info:
                company_id = item.get('company_id')
                expected_n_records = item.get('service_level_records')
                pub_item = item.get('service_level_pub_time')

                sql_query = """
                    SELECT count(*) as total_row
                    FROM service_level_result
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
            _logger.exception("An exception in check_status_of_update_service_level_result.", exc_info=True)
            raise
        return result, is_continue

    ###############################
    # API FUNCTIONS
    ###############################

    def get_json_required_fields(self, forecast_level, **kwargs):
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        # get required fields from forecast level
        required_fields_from_forecast_level = forecast_level_obj.get_required_fields()
        required_fields_of_models = [
            ("service_level", str, None)
        ]
        return required_fields_from_forecast_level + required_fields_of_models

    def transform_json_data_request(self, list_data, **kwargs):
        service_level_ids = self.env['service.level'].sudo().get_service_levels_ids()
        instantly_update = self.env['forecasting.config.settings'].sudo().check_instantly_update()
        for datum in list_data:
            datum = append_log_access_fields_to_data(self, datum)
            service_level = datum.pop("service_level", None)
            datum.update({
                'service_level_id': service_level_ids.get(service_level),
                'has_approved': instantly_update,
                'seq': datum.pop('order')
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
        self.update_service_level_in_product_classification_info(created_date=created_date,
                                                                 **{'forecast_level': forecast_level})

    def update_service_level_in_product_classification_info(self, created_date, **kwargs):
        forecast_level = kwargs.get('forecast_level')
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        # trigger the event to update the product information in the table ``product.classification.info``
        product_clsf_info_obj = self.env['product.classification.info'].sudo()

        # get new updated records through API
        new_records = forecast_level_obj.get_latest_records_dict_for_service_level_result(
            obj=self, model=self.env[self._name], created_date=created_date)
        number_of_record = len(new_records)

        from odoo.tools import config
        threshold_trigger_queue_job = config.get("threshold_to_trigger_queue_job",
                                                 DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB)

        if number_of_record < threshold_trigger_queue_job:
            product_clsf_info_obj.sudo() \
                .update_product_classification_infos(
                    json_data=new_records, recomputed_fields=['service_level_id'],
                    source_table='service_level_result',
                    **{
                        'forecast_level': forecast_level,
                        'created_date': created_date
                    }
                )
        else:
            product_clsf_info_obj.sudo().with_delay(max_retries=12)\
                .update_product_classification_infos(
                    json_data=new_records, recomputed_fields=['service_level_id'],
                    source_table='service_level_result',
                    **{
                        'forecast_level': forecast_level,
                        'created_date': created_date
                    }
                )

    ###############################
    # INITIAL FUNCTIONS
    ###############################
    @api.model
    def _create_service_level_result_indices(self):
        """
        Create indices in the table
        :return:
        """
        try:
            sql_query = """
                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_idx_service_level_result
                ON service_level_result (product_id, pub_time)
                WHERE company_id is NULL AND warehouse_id is NULL AND lot_stock_id is NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_idx_service_level_result
                ON service_level_result (product_id, company_id, pub_time)
                WHERE warehouse_id is NULL AND lot_stock_id is NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_warehouse_idx_service_level_result
                ON service_level_result (product_id, company_id, warehouse_id, pub_time);

                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_warehouse_lot_stock_idx_service_level_result
                ON service_level_result (product_id, company_id, warehouse_id, lot_stock_id, pub_time);

                CREATE UNIQUE INDEX IF NOT EXISTS service_level_result_product_id_company_id_warehouse_id
                ON service_level_result (product_id, company_id, warehouse_id, lot_stock_id, pub_time);                
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
