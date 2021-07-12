# -*- coding: utf-8 -*-

import json
import logging
import math

import requests

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from odoo.addons.queue_job.job import job

from odoo.addons.queue_job.exception import RetryableJobError

from odoo.addons.base.models.res_lang import DEFAULT_DATE_FORMAT
from odoo.addons.si_core.utils.request_utils import get_key_value_in_dict
from odoo.addons.si_core.utils import datetime_utils
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.forecast_base.utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB, ALLOW_TRIGGER_QUEUE_JOB
from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.addons.si_core.utils.database_utils import query

from datetime import datetime, date, timedelta

_logger = logging.getLogger(__name__)


class ProductForecastConfig(models.Model):
    _inherit = 'product.forecast.config'

    ###############################
    # JOB FUNCTIONS
    ###############################
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def generate_forecast_config_from_indirect_demand(self, updated_ids, company_id):
        """
            Create/Update the Product Forecast Configuration for all items have just update indirect demand

        :param list[int] updated_ids:
        :param int company_id:
        :return:
        :rtype:
        """
        try:
            # Step 1: check updated_ids whether is empty or not
            if updated_ids:


                # Step 3: generate the list of tuple key from forecast results daily
                # tuple_keys = [(frd.product_id.id, frd.company_id.id, frd.warehouse_id.id) for frd in daily_demands]
                # Step 3: get company info
                company = self.env['res.company'].browse(company_id)
                if company:
                    default_period_type = company.period_type
                    # Step 2: if the updated_ids is not empty, we find all forecast result daily from updated_ids
                    daily_demands = self.env['forecast.result_daily'].browse(updated_ids)
                    parsed_data = []
                    for demand in daily_demands:
                        parsed_data.append({
                            'product_id': demand.product_id.id,
                            'company_id': demand.company_id.id,
                            'warehouse_id': demand.warehouse_id.id,

                            'auto_update': False,
                            'period_type_custom': default_period_type,
                            'period_type': default_period_type,
                            'frequency_custom': default_period_type,
                            'frequency': default_period_type,
                            'no_periods_custom': 0
                        })

                    inserted_fields = ['product_id', 'company_id', 'warehouse_id', 'auto_update',
                                       'period_type_custom', 'period_type', 'frequency_custom',
                                       'frequency', 'no_periods_custom']
                    no_columns = len(inserted_fields)

                    query = """
                    INSERT INTO product_forecast_config
                            (product_id, company_id, warehouse_id, auto_update, period_type_custom, period_type, 
                            frequency_custom, frequency, no_periods_custom)
                            VALUES 
                            (%s)
                            ON CONFLICT (product_id, company_id, warehouse_id)
                            DO NOTHING;
                    """ % (
                        ','.join(inserted_fields),
                        ','.join(["%s"] * no_columns)
                    )
                    sql_params = [get_key_value_in_dict(item, inserted_fields) for item in parsed_data]
                    self.env.cur.executemany(query, sql_params)

                    from odoo.tools import config
                    threshold_trigger_queue_job = int(config.get('threshold_to_trigger_queue_job',
                                                                 DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
                    allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                         ALLOW_TRIGGER_QUEUE_JOB)

                    number_of_record = len(updated_ids)

                    if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                        self.env['forecast.result.adjust.line'].sudo() \
                            .with_delay(max_retries=12, eta=10) \
                            .update_indirect_demand_line(updated_ids)
                    else:
                        self.env['forecast.result.adjust.line'].sudo() \
                            .update_indirect_demand_line(updated_ids)

        except Exception:
            _logger.exception('Function generate_forecast_config_from_indirect_demand have some exception',
                              exc_info=True)
            raise RetryableJobError('Must be retried later')
