# -*- coding: utf-8 -*-

import logging
import psycopg2

from odoo import models, fields, api, _
from odoo.addons.si_core.utils.string_utils import get_table_name
from odoo.addons import decimal_precision as dp
from odoo.addons.si_core.utils.database_utils import get_db_cur_time, append_log_access_fields_to_data
from odoo.addons.si_core.utils.request_utils import get_key_value_in_dict

from ..utils.config_utils import ALLOW_TRIGGER_QUEUE_JOB

from time import time
from psycopg2 import IntegrityError

_logger = logging.getLogger(__name__)


class SummarizeRecResult(models.Model):
    """
    The class save the summarize result which receive for FE server
    """
    _name = "summarize.rec.result"
    _inherit = 'abstract.period.info'
    _description = "Summarize Result"

    ###############################
    # FIELDS
    ###############################
    summarize_value = fields.Float(required=True, readonly=True,
                                   digits=dp.get_precision('Product Unit of Measure'))
    no_picks = fields.Integer(required=True, readonly=True)
    picks_with_discount = fields.Integer(string='Picks With Discount', default=0, required=False)
    demand_with_discount = fields.Float(string='Demand With Discount', default=0.0, required=False,
                                        digits=dp.get_precision('Product Unit of Measure'))
    avg_discount_perc = fields.Float(string='Average Discount Percentage (%)', required=True, readonly=True,
                                     digits=dp.get_precision('Discount'))

    ###############################
    # API FUNCTIONS
    ###############################
    def get_json_required_fields(self, forecast_level, **kwargs):
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        # get required fields from forecast level
        required_fields_from_forecast_level = forecast_level_obj.get_required_fields()
        required_fields_of_models = [
            ('summarize_value', float, None),
            ('no_picks', int, None),
            ('picks_with_discount', int, None),
            ('demand_with_discount', float, None),
            ('avg_discount_perc', float, None),
        ]
        return required_fields_from_forecast_level + required_fields_of_models

    def transform_json_data_request(self, list_data, **kwargs):
        for datum in list_data:
            datum = append_log_access_fields_to_data(self, datum)

        return list_data

    def create_or_update_records(self, vals, forecast_level, **kwargs):
        converted_table_name = get_table_name(self._name)
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        try:
            # Run SQL code to update new data into the table
            # get insert fields from the data
            inserted_fields = list(vals[0].keys())

            # get conflict fields from forecast level
            conflict_fields = forecast_level_obj.get_conflict_fields_for_summarize_rec_result()
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
            _logger.info("data received %s .", vals)
            _logger.info("SQL %s.", self.env.cr.mogrify(sql_query, sql_params[0]).decode('utf-8'))
            _logger.info("Insert/update %s rows into the model.", len(vals))

        except IntegrityError:
            logging.exception("Duplicate key in the table %s: %s", converted_table_name, vals, exc_info=True)
            raise
        except Exception:
            _logger.exception("Error in the function create_or_update_records.", exc_info=True)
            raise

    def trigger_next_actions(self, created_date, **kwargs):
        forecast_level = kwargs.get('forecast_level')
        self.update_summarize_values_in_summarize_data_line(created_date=created_date,
                                                            **{'forecast_level': forecast_level})

    def update_summarize_values_in_summarize_data_line(self, created_date, **kwargs):
        forecast_level = kwargs.get('forecast_level')
        summarize_data_line_obj = self.env['summarize.data.line'].sudo()

        from odoo.tools import config
        allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                             ALLOW_TRIGGER_QUEUE_JOB)

        if allow_trigger_queue_job:
            summarize_data_line_obj.with_delay(max_retries=12)\
                .update_summarize_data(
                    created_date=created_date,
                    **{
                        'forecast_level': forecast_level
                    }
               )
        else:
            summarize_data_line_obj\
                .update_summarize_data(
                    created_date=created_date,
                    **{
                        'forecast_level': forecast_level
                    }
                )

    ###############################
    # INITIAL FUNCTIONS
    ###############################
    @api.model
    def create_unique_index_for_summarize_rec_result(self):
        try:
            sql_query = """
                CREATE UNIQUE INDEX IF NOT EXISTS unique_pid_cid_wid_summarize_rec_result_idx
                ON summarize_rec_result (product_id, company_id, warehouse_id, start_date, period_type, pub_time);               
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
