# -*- coding: utf-8 -*-

import psycopg2
import logging

from datetime import datetime

import numpy as np

from odoo.addons.queue_job.job import job

from odoo.addons.queue_job.exception import RetryableJobError
from psycopg2.extensions import AsIs

from odoo.addons.si_core.utils.string_utils import PeriodType
from ..utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB, ALLOW_TRIGGER_QUEUE_JOB

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ForecastResultDaily(models.Model):
    _name = "forecast.result.daily"
    _description = "Forecast Result Daily"
    _log_access = False

    ###################################
    # FIELDS
    ###################################
    forecast_adjust_line_id = fields.Many2one('forecast.result.adjust.line', required=True, ondelete='cascade',
                                              readonly=True)
    product_id = fields.Many2one(related='forecast_adjust_line_id.product_id', readonly=True, store=True)
    warehouse_id = fields.Many2one(related='forecast_adjust_line_id.warehouse_id', readonly=True, store=True)
    company_id = fields.Many2one(related='forecast_adjust_line_id.company_id', readonly=True, store=True)
    period_type = fields.Selection(PeriodType.LIST_PERIODS, readonly=True)
    date = fields.Datetime(readonly=True)
    daily_forecast_result = fields.Float(default=0.0, readonly=True,
                                         help='The total demand on this date')
    daily_sale_forecast_result = fields.Float(default=0.0, readonly=True,
                                              help='The sale demand on this date')
    active = fields.Boolean(default=False, readonly=True)
    _sql_constraints = [
        ('forecast_adjust_line_date_unique_key', 'unique (forecast_adjust_line_id, date)',
         'Forecast Adjust Line id and Date must be unique.'),
        ('unique_pwc_date_forecast_result_daily_idx', 'unique (product_id, warehouse_id, company_id, date)',
         'the set of company, warehouse, and product info combine with Date must be unique.'),
    ]

    ###################################
    # MODEL FUNCTIONS
    ###################################
    def get_all_daily_forecast_result_dict(self, product_ids=None):
        """ The function allows user get all daily forecast result shown by dictionary has
        key is tuple key of product_id, company_id, warehouse_id with the value is a list
        of FUTURE daily demand

        :return:
        Ex: {
                (product_id, company_id, warehouse_id): [
                    {
                        'product_id': 1,
                        'company_id': 2,
                        'warehouse_id': 3,
                        'date': '2020-11-24 00:00:00',
                        'daily_forecast_result': 123.456
                    }
                ]
            }
        :rtype: dict
        """
        extra_condition = ""
        if product_ids:
            extra_condition = self._cr.mogrify("""AND product_id in %s""", (tuple(product_ids),)).decode('utf-8')
        self._cr.execute("""
                SELECT product_id, company_id, warehouse_id, date, daily_forecast_result 
                FROM forecast_result_daily 
                WHERE active = TRUE AND date >= %(current_date)s %(extra_condition)s
                ORDER BY date
        """, {
            'current_date': datetime.now().date(),
            'extra_condition': AsIs(extra_condition)
        })
        all_daily_forecast_result_dict = {}

        for dr in self._cr.dictfetchall():
            key = (dr['product_id'], dr['company_id'], dr['warehouse_id'])
            all_daily_forecast_result = all_daily_forecast_result_dict.setdefault(key, [])
            all_daily_forecast_result.append(dr)
        return all_daily_forecast_result_dict

    @classmethod
    def get_sync_forecasting_result_fields(cls):
        """
        Get the fields need to update and the fields which can get updated value
        :return:
        :rtype: list[tuple]
        """
        return [('forecast_adjust_line_id', 'adjust.id'),
                ('product_id', 'adjust.product_id'),
                ('warehouse_id', 'adjust.warehouse_id'),
                ('company_id', 'adjust.company_id'),
                ('period_type', 'result.period_type'),
                ('active', 'True')]

    @classmethod
    def get_sync_forecasting_result_group_by_fields(cls):
        """
        Get the fields in group by clause when update forecasting daily
        :return:
        :rtype: list[tuple]
        """
        return ['adjust.id',
                'adjust.company_id',
                'adjust.warehouse_id',
                'adjust.product_id',
                'adjust.start_date',
                'result.period_type']

    def _convert_list_to_sql(self, objects):
        sql_format = ','.join(['%s'] * len(objects))

        sql_list = self.env.cr.mogrify(sql_format,
                                       [AsIs(object) for object in objects]).decode('utf-8')

        return sql_list

    def update_daily_forecast_result(self, forecasting_value, forecast_adjust_line_id):
        """
        Update daily forecast result when the user change the forecast result in Product Page/Forecast Review
        :param forecasting_value:
        :type forecasting_value: float
        :param forecast_adjust_line_id:
        :type forecast_adjust_line_id: int
        :return: None
        """
        try:
            sql_query = """
                UPDATE forecast_result_daily daily
                SET daily_forecast_result = CASE daily.period_type
                WHEN
                  'weekly' THEN %(forecasting_value)s/7.0
                WHEN
                  'monthly' THEN %(forecasting_value)s/30.0
                WHEN
                  'quarterly' THEN %(forecasting_value)s/90.0
                END
                WHERE forecast_adjust_line_id = %(adjust_line_id)s;
            """

            if type(forecasting_value) is list and type(forecast_adjust_line_id) is list:
                sql_params = [{
                    'forecasting_value': item[0], 'adjust_line_id': item[1]
                } for item in zip(forecasting_value, forecast_adjust_line_id)]
            else:
                sql_params = [{
                    'forecasting_value': forecasting_value,
                    'adjust_line_id': forecast_adjust_line_id
                }]

            self.env.cr.executemany(sql_query, sql_params)
            self.env.cr.commit()

        except Exception as e:
            _logger.exception("Exception in update_daily_forecast_result: %r" % (e,), exc_info=True)

    def update_status_of_records(self, line_ids, is_active=True):
        sql_query = """
            UPDATE forecast_result_daily SET active = %s WHERE forecast_adjust_line_id IN %s;
        """
        sql_params = [is_active, tuple(line_ids)]
        self.env.cr.execute(sql_query, sql_params)
        self.env.cr.commit()

    def convert_forecast_result_to_daily_value(self, fral_ids):
        """
        Convert forecast value from the table Forecast Result Adjust Line to daily value
        base on each period type and store to the table forecast result daily
        :param list[int] fral_ids: list of record id in the table Forecast Result Adjust Line
        :return None:
        """
        unique_fral_ids = np.unique(fral_ids).tolist()

        # get company_id from ids of Forecast Result Adjust Line
        frals = self.env['forecast.result.adjust.line'].search_read([('id', 'in', unique_fral_ids)],
                                                                    ['id', 'company_id'])

        fral_records = [{
            'id': record.get('id'),
            'company_id': record.get('company_id')[0]
        } for record in frals]

        company_ids = list(set([item.get('company_id') for item in fral_records]))

        forecast_level_dict = self.env['res.company'].sudo().get_forecast_level_by_company(company_ids=company_ids)
        forecast_level_strategy_obj = self.env['forecast.level.strategy']
        _logger.info("Forecast level config in convert_forecast_result_to_daily_value: %s", forecast_level_dict)

        for company_id, forecast_level in forecast_level_dict.items():
            forecast_level_obj = forecast_level_strategy_obj.create_obj(forecast_level=forecast_level)

            # filter data by company_id
            filtered_fral_ids = [item.get('id') for item in fral_records if item.get('company_id') == company_id]
            _logger.info("Convert to daily forecast value with fral ids of company %s: %s", company_id,
                         filtered_fral_ids)

            if filtered_fral_ids:
                forecast_level_obj.create_or_update_records_in_forecast_result_daily(obj=self, model_name=self._name,
                                                                                     line_ids=filtered_fral_ids)
        self.rounding_forecast_value(unique_fral_ids)

    def rounding_forecast_value(self, line_ids=None):
        """

        :return:
        """
        if line_ids:
            self._cr.execute("""
                    UPDATE forecast_result_daily frd
                    SET daily_forecast_result = round(daily_forecast_result/rounding) * rounding
                    FROM forecast_result_adjust_line line 
                      JOIN product_product prod
                        ON line.product_id = prod.id
                      JOIN product_template tmpl
                        ON prod.product_tmpl_id = tmpl.id
                      JOIN uom_uom uu
                        ON tmpl.uom_id = uu.id
                    WHERE frd.forecast_adjust_line_id = line.id AND line.id IN %s AND prod.id = line.product_id;""",
                             (tuple(line_ids), ))
            self._cr.commit()

    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_forecast_result_daily(self, line_ids, call_from_engine=False):
        """ The function update the forecast result daily for products have just updated
        the forecast result (in the table forecast_result_adjust_line)

        :param list[int] line_ids: forecast result adjust lines id
        :param bool call_from_engine:
        :return:
        """
        _logger.info("Update forecast result daily with line ids: %s", line_ids)
        try:
            # mark rows are processing
            self.update_status_of_records(line_ids, is_active=False)
            self.convert_forecast_result_to_daily_value(fral_ids=line_ids)
            # mark rows are done
            self.update_status_of_records(line_ids, is_active=True)

            # update forecast.result.adjust table
            number_of_record = len(line_ids)

            from odoo.tools import config
            threshold_trigger_queue_job = int(config.get('threshold_to_trigger_queue_job',
                                                         DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
            allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                 ALLOW_TRIGGER_QUEUE_JOB)

            if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                self.env['forecast.result.adjust'].sudo().with_delay(max_retries=12). \
                    update_forecast_result_base_on_lines(line_ids, update_time=True, call_from_engine=call_from_engine)
            else:
                self.env['forecast.result.adjust'].sudo() \
                    .update_forecast_result_base_on_lines(line_ids, update_time=True, call_from_engine=call_from_engine)

        except Exception as e:
            _logger.exception("function update_forecast_result_daily have some exception: %s" % e)
            raise RetryableJobError('Must be retried later')
