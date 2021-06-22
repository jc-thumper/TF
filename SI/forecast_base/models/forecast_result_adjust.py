# -*- coding: utf-8 -*-

import json
import logging
import math
from datetime import datetime
from time import sleep

from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.addons.si_core.utils import datetime_utils, database_utils
from psycopg2.extensions import AsIs

from ..utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB

from odoo import models, fields, api

from odoo.addons.queue_job.job import job
from odoo.addons.queue_job.exception import RetryableJobError

_logger = logging.getLogger(__name__)


class ForecastResultAdjust(models.Model):
    _name = "forecast.result.adjust"
    _inherit = 'abstract.product.info'
    _description = "Forecasting Adjustment Info"

    ###############################
    # CONSTANTS
    ###############################
    NO_PERIODS = 12
    PERCENT_PAST = 0.5
    PAST_PERIODS = math.ceil(NO_PERIODS * PERCENT_PAST)
    FUTURE_PERIODS = NO_PERIODS - PAST_PERIODS

    ###############################
    # FIELDS
    ###############################
    period_type = fields.Selection(PeriodType.LIST_PERIODS)

    actual_chart_data = fields.Char(compute='_compute_actual_chart_data', string='Historical Demand',
                                    help='The history demand', store=True)
    forecast_chart_data = fields.Char(compute='_compute_forecast_chart_data', string='Future Demand',
                                      help='The future demand, that base on the forecast value', store=True)
    demand_chart = fields.Char(compute='_compute_demand_chart', string='',
                               help='The chart combine historical demand and forecast data', store=True)

    adjust_line_ids = fields.One2many('forecast.result.adjust.line', 'forecast_result_adjust_id')

    last_update = fields.Date(store=True,
                              help='The Last Time update the forecast result value '
                                   '(from cron job/adjust_line/forecast_daily)')

    last_receive_result = fields.Date(store=True,
                                      help='The Last Time receive result from forecast engine')

    has_forecasted = fields.Boolean(compute='_compute_has_forecasted', search='_search_has_forecasted')

    _sql_constraints = [
        ('pcw_pt_uniq',
         'unique (product_id, company_id, warehouse_id, period_type)',
         'The tuple product, company, warehouse id, and period_type '
         'must be unique within table forecast_result_adjust in an application!')
    ]

    ###############################
    # COMPUTE FUNCTIONS
    ###############################
    @api.depends('adjust_line_ids', 'adjust_line_ids.forecast_line_id')
    def _compute_has_forecasted(self):
        for fra in self:
            has_forecasted = False
            for line in fra.adjust_line_ids:
                if line.forecast_result is not None:
                    has_forecasted = True
                    break
            fra.has_forecasted = has_forecasted

    @api.depends('adjust_line_ids.adjust_value', 'adjust_line_ids.demand_adjust_value')
    def _compute_actual_chart_data(self):
        start_date_previous_period_dict = ForecastResultAdjust.get_start_date_previous_period_dict()
        decimal_pre = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        for fra in self:
            period_type = fra.period_type
            start_date_previous_period = start_date_previous_period_dict.get(period_type)

            history_fral = fra.adjust_line_ids.filtered(
                lambda fral: fral.start_date <= start_date_previous_period)

            old_forecast = []
            if history_fral:
                for fral in history_fral:
                    if fral.start_date <= start_date_previous_period:
                        label = PeriodType.generate_period_label(fral.start_date, fral.end_date, fral.period_type)

                        old_forecast.append({
                            'x': fral.start_date.strftime('%Y-%m-%d'),
                            'name': label,
                            'y': ForecastResultAdjust.get_demand_value_to_update_actual_chart(
                                record=fral,
                                precision_digits=decimal_pre
                            )
                        })

            fra.actual_chart_data = json.dumps(
                {
                    'key': 'Actual',
                    'color': '#5DADE2',
                    'title': 'Real Data result',
                    'area': False,
                    'values': old_forecast
                }
            )

    @api.depends('adjust_line_ids.adjust_value', 'adjust_line_ids.demand_adjust_value')
    def _compute_forecast_chart_data(self):
        """

        :return:
        """
        start_date_previous_period_dict = ForecastResultAdjust.get_start_date_previous_period_dict()
        decimal_pre = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        for fra in self:
            period_type = fra.period_type
            start_date_previous_period = start_date_previous_period_dict.get(period_type)

            future_fral = fra.adjust_line_ids.filtered(
                lambda line: line.start_date >= start_date_previous_period)

            new_forecast = []
            if future_fral:
                for fral in future_fral:
                    start_date = fral.start_date
                    label = PeriodType.generate_period_label(fral.start_date, fral.end_date, fral.period_type)
                    x = start_date.strftime('%Y-%m-%d')

                    if start_date == start_date_previous_period:
                        new_forecast.append({
                            'x': x,
                            'name': label,
                            'y': ForecastResultAdjust.get_demand_value_to_update_actual_chart(
                                record=fral,
                                precision_digits=decimal_pre
                            )
                        })

                    elif start_date > start_date_previous_period:
                        new_forecast.append({
                            'x': x,
                            'name': label,
                            'y': round(fral.adjust_value, decimal_pre)
                        })

            fra.forecast_chart_data = json.dumps(
                {
                    'color': '#A04000',
                    'show_legend': True,
                    'key': 'Forecast',
                    'title': 'Forecasting Data result',
                    'area': False,
                    'classed': 'dashed',
                    'values': new_forecast
                }
            )

    @api.depends('actual_chart_data', 'forecast_chart_data')
    def _compute_demand_chart(self):
        for fra in self:
            if fra.has_forecasted:
                lines_data = [json.loads(fra.actual_chart_data)] if fra.actual_chart_data else []
                lines_data += [json.loads(fra.forecast_chart_data)] if fra.forecast_chart_data else []
                fra.demand_chart = json.dumps(
                    {
                        'title_x': 'Date time (YYYY-MM-DD)',
                        'name_chart': '',
                        'title_y': 'Quantity (items)',
                        'data': lines_data
                    }
                )
            else:
                fra.demand_chart = False

    ###############################
    # SEARCH FUNCTIONS
    ###############################
    def _search_has_forecasted(self, operator, value):
        if operator not in ('=', '!='):
            raise ValueError('Invalid operator: %s' % (operator,))
        fras_have_forecasted = self
        for fra in self.search([]):
            for line in fra.adjust_line_ids:
                if line.forecast_line_id:
                    fras_have_forecasted += fra
                    break
        operator = 'in' if (operator == '=' and value) or (operator == '!=' and not value) else 'not in'
        return [('id', operator, fras_have_forecasted.ids)]

    ###############################
    # HELPER FUNCTIONS
    ###############################
    @staticmethod
    def get_start_date_previous_period_dict():
        """
            This function helps to return the start_date of the previous period for every period's type
        :param string period_type:
        :return:
        Ex: {
            'daily': datetime,
            'weekly': datetime,
            ...
        }
        :rtype: dict
        """
        datetime_now = datetime.now()

        start_date_previous_period_dict = {}
        for period_type, period_text in PeriodType.LIST_PERIODS:
            start_date_previous_period_dict.setdefault(
                period_type,
                datetime_utils.get_start_end_date_value(
                    datetime_now + datetime_utils.get_delta_time(period_type, -1),
                    period_type
                )[0].date()
            )

        return start_date_previous_period_dict

    def get_no_available_adjust_items(self, pub_time):
        """
        Get number of records of Forecast Result Adjust Line
        :param pub_time: the lasted pub_time from table Forecast Result
        :type pub_time: str
        :return: The number of nearest forecast results
        :rtype: int
        """
        result = 0
        try:
            sql_query = """    
                select
                    fral.product_id, fral.company_id, fral.warehouse_id, fr.pub_time, count(*)
                from forecast_result_adjust_line fral
                inner join (select id from forecast_result_adjust where demand_chart is not null) fra 
                    on fral.forecast_result_adjust_id = fra.id
                inner join (select id, pub_time from forecast_result where pub_time = %s) fr 
                    on fral.forecast_line_id = fr.id
                group by fral.product_id, fral.company_id, fral.warehouse_id, fr.pub_time;
            """
            sql_param = (pub_time,)
            self.env.cr.execute(sql_query, sql_param)
            records = self.env.cr.dictfetchall()
            result = len(records)
            _logger.info("Number records in forecast_result_adjust_line with forecast result at %s: %s",
                         pub_time, result)
            return result
        except Exception as e:
            _logger.exception("An exception in get_no_available_adjust_items", exc_info=True)
            raise e

    def recompute_actual_chart_data(self):
        self._compute_actual_chart_data()

    def recompute_forecast_chart_data(self):
        self._compute_forecast_chart_data()

    def update_adjust_line_ids(self):
        """

        :return: None
        """
        for fra in self:
            # Step 1: Clear the id of forecast_result_adjust record in lines
            # of forecast_result_adjust_line table
            lines = self.env['forecast.result.adjust.line'] \
                .search([('forecast_result_adjust_id', '=', fra.id)])
            lines.write({'forecast_result_adjust_id': None})

            # Step 2: Update the id forecast_result_adjust for any suit
            # rows in table forecast_result_adjust_line
            past_period = self.env['res.config.settings'].get_past_periods()
            future_period = self.env['res.config.settings'].get_future_periods()

            period_type = fra.period_type
            cur_first_date = datetime_utils.get_start_end_date_value(datetime.now(), period_type)[0]
            start_first_date = cur_first_date - datetime_utils.get_delta_time(
                period_type,
                past_period)
            end_first_date = cur_first_date + datetime_utils.get_delta_time(
                period_type,
                future_period)

            self.env['forecast.result.adjust.line'] \
                .search([('product_id', '=', fra.product_id.id),
                         ('company_id', '=', fra.company_id.id),
                         ('warehouse_id', '=', fra.warehouse_id.id),
                         ('period_type', '=', period_type),
                         ('start_date', '>=', start_first_date.date()),
                         ('end_date', '<', end_first_date.date())]) \
                .write({'forecast_result_adjust_id': fra.id})

    def update_adjust_related_info(self, call_from_engine=False):
        """ Function update normal fields (to separate with standard fields pid, wid, cid,...)

        :param call_from_engine:
        :type call_from_engine: bool
        :return:
        :rtype:
        """
        date_now = datetime.now().date()
        self.update_adjust_line_ids()

        update_data = {'last_update': date_now}
        if call_from_engine:
            update_data.update({'last_receive_result': date_now})
        self.write(update_data)

        self.update_chart()

    def update_chart(self):
        """

        :return:
        :rtype: None
        """
        for fra in self:
            with fra.env.norecompute():
                fra.recompute_actual_chart_data()
                fra.recompute_forecast_chart_data()
            fra.recompute()
            fra._compute_demand_chart()
            fra.write({
                'actual_chart_data': fra.actual_chart_data,
                'forecast_chart_data': fra.forecast_chart_data,
                'demand_chart': fra.demand_chart
            })

    @staticmethod
    def get_demand_value_to_update_actual_chart(record, precision_digits=None):
        """
        Get demand value to update the demand in the past in Demand Forecast chart
        :param record: a record to get the data to show in the chart
        :type record: record
        :param precision_digits: number of digits
        :type: int
        :return: the new demand to show in the chart
        :rtype: float
        """
        result = 0
        if record:
            result = round(record.demand_adjust_value, precision_digits)
        return result

    ###############################
    # PRIVATE FUNCTIONS
    ###############################
    def _update_forecast_result(self, lines, update_time=False, call_from_engine=False):
        """ Function update table `forecast_result_adjust` base on `lines`,
        Run when (create/adjust forecast_result_adjust_line, forecast_result_daily)

        :param call_from_engine:
        :param lines:
        :type lines: list(forecast.result.adjust.line)
        :param update_time:
        :return:
        :rtype: recordset
        """
        fra_obj = None
        if lines:
            cur_info_dict, fral_list_dict = self._gen_dict_adjust_line(lines)

            # Step 1: create new rows in table forecast result adjust with general info
            write_time = self._create_new_fore_res_adjust(fral_list_dict.keys())

            fra_obj = self.search([('write_date', '=', write_time)])
            # Step 2: update the chart
            fra_obj.update_adjust_related_info(call_from_engine)

        return fra_obj

    @api.model
    def _list_key_columns(self, cid):
        """

        :return:
        :rtype: list[str]
        """
        key_columns = []

        company_id = self.env['res.company'].sudo().search([('id', '=', cid)])
        if company_id:
            forecast_level_id = company_id.forecast_level_id

            _logger.info('forecast result adjust forecast level is %s' % forecast_level_id.name)
            key_columns = forecast_level_id.get_object().get_full_keys() + ['period_type']

        return key_columns

    @api.model
    def _list_constrain_columns(self, cid):
        """

        :return:
        :rtype: list[str]
        """

        forecast_level = self.env['res.company'].sudo().search([('id', '=', cid)]).forecast_level_id

        key_columns = forecast_level.get_list_of_extend_keys() + ['period_type']
        _logger.info('List of constrain columns use for forecast adjust is %s' % key_columns)

        return key_columns

    def _create_new_fore_res_adjust(self, keys_tuple):
        """ All the row in keys_tuple have same company
        Function create new rows, which have been not existed before, of
        table `forecast.result.adjust`

        :param keys_tuple: list of tuples of key, which are used to
        create new record have been not existed before, having structure is:
            (product_id, company_id, warehouse_id, period_type)
        :type keys_tuple: list(tuple)
        :return:
        """
        cur_time = database_utils.get_db_cur_time(self.env.cr)

        chunk_size = 200
        i = 0
        max_time_fail = 5
        count_time_fail = 0
        chunks = math.ceil(len(keys_tuple) / chunk_size)
        latest_updated_records_list = list(keys_tuple)

        log_info = [self.env.ref('base.partner_root').id, cur_time,
                    self.env.ref('base.partner_root').id, cur_time]

        while i < chunks:
            i += 1
            try:
                upper_bound = chunk_size * i if i < chunks else len(keys_tuple)
                sub_records = latest_updated_records_list[chunk_size * (i - 1): upper_bound]
                key_columns = self._list_key_columns(sub_records[0][1])
                key_columns_str = ', '.join(key_columns)

                constrain_columns = self._list_constrain_columns(sub_records[0][1])
                constrain_columns_str = ', '.join(constrain_columns)
                rowf = '(' + ', '.join(['%s'] * (len(sub_records[0]) + 4)) + ')'
                query = """
                    INSERT INTO forecast_result_adjust (
                    {key_columns},
                    create_uid, create_date, write_uid, write_date)
                    VALUES {rows}
                    ON CONFLICT ({constrain_columns})
                    DO UPDATE SET write_date = EXCLUDED.write_date;
                           """.format(
                    key_columns=AsIs(key_columns_str),
                    constrain_columns=AsIs(constrain_columns_str),
                    rows=", ".join([rowf] * len(sub_records)),
                )
                record_data = [arg
                               for row in sub_records
                               for arg in (list(row) + log_info)]

                try:
                    self.env.cr.execute(query, record_data)
                    self.env.cr.commit()
                    sleep(0.5)
                except Exception:
                    _logger.error('Failed to insert forecast_result_adjust\n%s',
                                  '\n'.join(str(row) for row in sub_records))
                    raise

                count_time_fail = 0

            except Exception as e:
                _logger.exception(e)
                sleep(10)
                count_time_fail += 1
                if count_time_fail < max_time_fail:
                    i -= 1
                else:
                    _logger.exception('Write data to forecast_result_adjust fail over %s times' % max_time_fail)

            # Step: get latest forecast result
            fore_result_adjust = self.search([('write_date', '=', cur_time)])

            # Step: recompute computed fields
            fore_result_adjust \
                .modified(key_columns)

            self.env.cr.commit()

            number_of_record = len(fore_result_adjust)

            from odoo.tools import config
            threshold_trigger_queue_job = int(config.get("threshold_to_trigger_queue_job",
                                                         DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))

            if number_of_record < threshold_trigger_queue_job:
                self.env['product.forecast.config'].sudo() \
                    .update_execute_date(fore_result_adjust.ids, cur_time)
            else:
                self.env['product.forecast.config'].sudo() \
                    .with_delay(max_retries=12).update_execute_date(fore_result_adjust.ids, cur_time)

        return cur_time

    def _gen_dict_adjust_line(self, frals):
        """

        :param frals:
        :return: tuple(dict(period_type:, {
                    'cur_first_date': cur_first_date,
                    'start_first_date': start_first_date,
                    'end_first_date': end_first_date,
                }), dict(key_tuple, frals))
        :rtype: tuple(dict(dict()), dict(recordset))
        """
        cur_info_dict = {}
        fral_list_dict = {}
        res_config_setting_env = self.env['res.config.settings']
        for fral in frals:
            period_type = fral.period_type
            cur_period_info = cur_info_dict.get(period_type)

            # init period information
            if not cur_period_info:
                cur_first_date = datetime_utils.get_start_end_date_value(datetime.now(), period_type)[0]
                past_period = res_config_setting_env.get_past_periods()
                future_periods = res_config_setting_env.get_future_periods()

                start_first_date = cur_first_date - datetime_utils.get_delta_time(
                    period_type,
                    past_period)
                end_first_date = cur_first_date + datetime_utils.get_delta_time(
                    period_type,
                    future_periods - 1)

                cur_period_info = {
                    'cur_first_date': cur_first_date,
                    'start_first_date': start_first_date,
                    'end_first_date': end_first_date,
                }
                cur_info_dict[period_type] = cur_period_info

            keys_tuple = fral._get_tuple_key() + (period_type, )
            fral_list = fral_list_dict.get(keys_tuple, self.env['forecast.result.adjust.line'])
            fral_list += fral
            fral_list_dict[keys_tuple] = fral_list
        return cur_info_dict, fral_list_dict

    ###############################
    # CRON FUNCTIONS
    ###############################
    def run_scheduler_update_fore_res_adj(self, ignore_latest_update=False):
        """ Just Run when cron job automatically run to update chart

        :param ignore_latest_update: fras will be updated event though last update
        still not out update when `ignore_latest_update` is True
        :type ignore_latest_update: bool
        :return:
        """
        for period_type, _ in PeriodType.LIST_PERIODS:
            # Step 1: get first date of current period
            first_date = datetime_utils.get_start_end_date_value(datetime.now(), period_type)[0]

            # Step 2: create domain and
            last_update_domain = [] \
                if ignore_latest_update \
                else ['|', ('last_update', '<=', first_date.date()), ('last_update', '=', None)]
            fras_domain = last_update_domain + [('period_type', '=', period_type)]

            # Step 3: search any forecast result adjust item have been satisfied
            fras = self.search(fras_domain)
            fras.update_adjust_related_info()

    ###############################
    # JOB FUNCTIONS
    ###############################
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_forecast_result_base_on_lines(self, line_ids, update_time=False, call_from_engine=False):
        """ Function update table `forecast_result_adjust` base on `lines`,
        Run when (create/adjust forecast_result_adjust_line, forecast_result_daily)

        :param list[int] line_ids:
        :param bool update_time:
        :param bool call_from_engine:
        :return:
        """
        try:
            # NOTE: avoid using the method ``browse``, this function still return a record set for all record
            # even if this record id doesn't exits in the database
            lines = self.sudo().env['forecast.result.adjust.line'].search([('id', 'in', line_ids)])
            self._update_forecast_result(lines, update_time, call_from_engine)
        except Exception as e:
            _logger.exception('function update_forecast_result_base_on_lines have some exception: %s' % e)
            raise RetryableJobError('Must be retried later')
