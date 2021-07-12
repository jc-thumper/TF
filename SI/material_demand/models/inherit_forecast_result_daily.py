# -*- coding: utf-8 -*-

import logging
import math

import pandas as pd

from datetime import datetime, timedelta

from odoo import models, fields, api

from odoo.osv import expression
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

from odoo.addons.queue_job.job import job
from odoo.addons.queue_job.exception import RetryableJobError

from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.addons.si_core.utils import database_utils
from odoo.addons.si_core.utils.request_utils import get_key_value_in_dict

from ..utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB, ALLOW_TRIGGER_QUEUE_JOB

_logger = logging.getLogger(__name__)


class InheritForecastResultDaily(models.Model):
    _inherit = 'forecast.result.daily'

    ###################################
    # FIELDS
    ###################################
    include_indirect_demand = fields.Boolean(default=False, readonly=True)
    indirect_demand = fields.Float(default=0)
    detail_indirect_demand = fields.Char('Detail Indirect Demand')

    ###################################
    # PRIVATE FUNCTIONS
    ###################################
    def _update_indirect_dict(self, indirect_demand_dict, finished_id, finish_good_demand,
                              date_check, company_id, warehouse_id, daily_demand_id):
        """ The function update data for dictionary indirect_demand_dict

        :param dict indirect_demand_dict: the dictionary store the indirect demand of the
        list of products that is the direct or indirect material of current finished good.
        This variable store the daily demand; this dictionary is Empty at the beginning
        Ex: {
                (product_id, company_id, warehouse_id, daily_demand_id, bom_info_id): {
                    date_1: 0,
                    date_2: 0,
                    date_3: 1,
                }
            }
        :param ProductProduct finished_id:
        :param float finish_good_demand:
        :param datetime date_check: the date that is used to compute the demand of the finished_id
        :param int daily_demand_id: id of forecast result adjust line
        :return: None
        """
        # finding all BoMs this finished good
        bom_info_ids = self.env['product.bom.info']\
            .search([('target_product_id', '=', finished_id.id)])

        for bom_info in bom_info_ids:
            bom_info_id = bom_info.id
            product_unit_qty = bom_info.material_factor
            material = bom_info.product_id

            produce_delay = bom_info.produce_delay

            po_perc = finished_id.po_perc
            manufacturing_demand = finish_good_demand * (1 - po_perc/100.0)

            # The number of Unit of BoMs that we need to make MO
            material_qty_raw = math.ceil(manufacturing_demand / product_unit_qty)

            material_qty = float_round(
                material_qty_raw,
                precision_rounding=material.uom_id.rounding,
                rounding_method='UP')

            date_check_point = date_check + timedelta(days=produce_delay)

            material_key = (material.id, company_id, warehouse_id) + (daily_demand_id, bom_info_id,)
            material_demand_dict = indirect_demand_dict.setdefault(material_key, {})
            material_demand_dict[date_check_point] = material_qty

    @staticmethod
    def _gen_product_forecast_config_domain(keys):
        list_domain_items = []
        for key in keys:
            list_domain_items.append(expression.AND([
                [('product_id', '=', key[0])],
                [('company_id', '=', key[1])],
                [('warehouse_id', '=', key[2])]
            ]))
        domain = expression.OR(list_domain_items)
        return domain

    @staticmethod
    def _get_item_keys(indirect_demand_dict):
        """

        :param indirect_demand_dict:
        :return list[tuple]:
        """
        keys = []
        for key in indirect_demand_dict.keys():
            keys.append((key[0], key[1], key[2]))
        return keys

    def _get_period_dict(self, indirect_demand_dict):
        """ Get the dictionary of the list of items have same period type from table product_forecast_config

        :param dict indirect_demand_dict:
        :return dict: dictionary of key is the period type and value is the list of item key
        Ex: {
                'weekly': [(pid, cid, wid), ...]
            }
        :rtype: dict
        """
        period_dict = {}

        keys = self._get_item_keys(indirect_demand_dict)
        domain = self._gen_product_forecast_config_domain(keys)
        product_forecast_configs = self.env['product.forecast.config'].search(domain)

        existed_keys = {}
        for pfc in product_forecast_configs:
            period_type = pfc.period_type_custom
            items = period_dict.setdefault(period_type, [])
            tuple_key = (pfc.product_id and pfc.product_id.id or False,
                         pfc.company_id and pfc.company_id.id or False,
                         pfc.warehouse_id and pfc.warehouse_id.id or False)
            existed_keys |= {tuple_key}
            items.append(tuple_key)

        remain_keys = set(keys) - existed_keys

        if remain_keys:
            items = period_dict.setdefault(PeriodType.DEFAULT_PERIOD_TYPE, [])
            for key in remain_keys:
                items.append(key)
        return period_dict

    def _get_detail_stock_demand_insert_data(self, indirect_demand_dict):
        """ The function convert the data in variable indirect_demand_dict to the list of dictionary
        that we use to insert to the table forecast_result_adjust_line

        Assumption:
            - all items in indirect_demand_dict have same company_id that the value we push in the param
            get corresponding strategy

        :param dict indirect_demand_dict: the dictionary contain the indirect demand computed from
        the direct of the finished good demand
        Ex: {
                (product_id, company_id, warehouse_id, daily_demand_id, bom_info_id): {
                    date_1: 0,
                    date_2: 0,
                    date_3: 1,
                }
            }
        :return list[dict]: the list of dictionary contain data to write to table forecast_result_adjust_line
        Ex: [
                {
                    'product_id': 1,
                    'company_id': 1,
                    'warehouse_id': 1,
                    'date': 2021-06-29 00:00:00.000000,
                    'active': True,
                    'include_indirect_demand': True,
                    'indirect_demand': 123.456,
                    'detail_indirect_demand': '{
                        daily_demand_id1: 100,
                        daily_demand_id2: 20,
                        daily_demand_id3: 0.456,
                    }'
                },...
            ]
        """
        insert_data = []
        insert_data_dict = {}
        for keys, daily_demand in indirect_demand_dict.items():
            product_id = keys[0]
            company_id = keys[1]
            warehouse_id = keys[2]
            daily_demand_id = keys[3]
            new_key = (keys[0])
        # define variable
        period_dict = self._get_period_dict(indirect_demand_dict)
        detail_demand_df = pd.DataFrame(indirect_demand_dict)

        df_freq_str_dict = dict([
            (PeriodType.DAILY_TYPE, 'D'),
            (PeriodType.WEEKLY_TYPE, 'W'),
            (PeriodType.MONTHLY_TYPE, 'M'),
            (PeriodType.QUARTERLY_TYPE, 'Q'),
            (PeriodType.YEARLY_TYPE, 'Y')])
        insert_data = []

        # list_items is the list of tuple key (product_id, company_id, warehouse_id)
        for period_type, list_items_key in period_dict.items():

            df_freq_str = df_freq_str_dict[period_type]
            # TODO: here
            item_data_df = pd.concat([detail_demand_df[item_key] for item_key in list_items_key], axis=1)

            # convert Timestamps to datetime
            item_data_df.index = pd.to_datetime(item_data_df.index)

            # Group by sum for the demand data with the period type
            sum_data = item_data_df.resample(df_freq_str).sum()
            no_items = sum_data.shape[1]
            sum_data = sum_data.reset_index()
            date_series = pd.Series(sum_data['index'])
            period = date_series.dt.to_period(df_freq_str)

            #
            sum_data['period'] = period
            sum_data['start_date'] = period.apply(lambda r: r.start_time)
            sum_data['end_date'] = period.apply(lambda r: r.end_time)
            sum_data.pop('index')
            sum_data_dict = sum_data.to_dict('split')

            columns = sum_data_dict['columns']
            start_date_index = columns.index(('start_date', ''))
            end_date_index = columns.index(('end_date', ''))

            for row_index, cols_value in enumerate(sum_data_dict.get('data')):
                start_date = cols_value[start_date_index].date()
                end_date = cols_value[end_date_index].date()
                for col_index, value in enumerate(cols_value):
                    if col_index < no_items:
                        for key, demand in value.items():
                            insert_data.append({
                                'source_line_id': key[0],
                                'affected_line_id': '',
                                'prod_bom_id': key[1],
                                'start_date': str(start_date),
                                'end_date': str(end_date),
                                'period_type': period_type,
                                'forecast_result': value,
                                'adjust_value': value,
                                'indirect_forecast': value,
                                'fore_pub_time': str(pub_time),
                            })

        return insert_data

    def _create_update_detail_material_demand(self, insert_data):
        """ The function update the detail of indirect demand to the table detail_stock_demand

        :param list[dict] insert_data:
        Ex: [
                {
                    'product_id': 1,
                    'company_id': 1,
                    'warehouse_id': 1,
                    'date': 2021-06-29 00:00:00.000000,
                    'active': True,
                    'include_indirect_demand': True,
                    'indirect_demand': 123.456,
                    'detail_indirect_demand': '{
                        daily_demand_id1: 100,
                        daily_demand_id2: 20,
                        daily_demand_id3: 0.456,
                    }'
                },...
            ]
        :return list[int]: return to the list of detail_stock_demand id
        """
        updated_ids = []
        try:
            if insert_data:
                n_records = len(insert_data)

                # get insert fields from the data
                inserted_fields = list(insert_data[0].keys())
                no_columns = len(inserted_fields)

                sql_query = """
                        INSERT INTO forecast_result_daily
                        (%s)
                        VALUES 
                        (%s)
                        ON CONFLICT (product_id, warehouse_id, company_id, date)
                        DO UPDATE SET 
                            include_indirect_demand = EXCLUDED.include_indirect_demand,
                            indirect_demand         = EXCLUDED.indirect_demand,
                            detail_indirect_demand  = (CASE WHEN detail_indirect_demand IS NULL 
                                    OR detail_indirect_demand = '' 
                                THEN '{}' 
                                ELSE detail_indirect_demand END)::jsonb || EXCLUDED.detail_indirect_demand::jsonb,
                            active                  = True
                        RETURNING id;
                """ % (
                    ','.join(inserted_fields),
                    ','.join(["%s"] * no_columns)
                )

                sql_params = [get_key_value_in_dict(item, inserted_fields) for item in insert_data]
                self.env.cr.executemany(sql_query, sql_params)

                updated_ids = [item.get('id') for item in self.env.cr.dictfetchall()]

                logging.info("Finish insert %d new indirect demands into the table forecast_result_daily."
                             % n_records)
            else:
                logging.info("Don't have any forecast item will be updated to the forecast result daily table.")
        except Exception as e:
            _logger.exception("Error in the function _create_update_detail_material_demand.", exc_info=True)
            raise e
        return updated_ids

    ###################################
    # JOB FUNCTIONS
    ###################################
    @api.model
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_daily_material_indirect_demand(self, daily_results):
        """ Update the daily Material Indirect Demand from the daily demand of their finished goods after it's updated
        this is assume all lines in have same company

        :param list[int] daily_results:
        :return None:
        """
        try:
            indirect_demand_dict = {}

            # Step 1: get the list of forecast result adjust lines are writen at ``write_time``
            daily_results = self.search([('forecast_adjust_line_id', '=', daily_results)])
            if daily_results:
                demand = daily_results[0]
                # The fist line always have the company info and the forecast pub time because
                # this function is just triggered right after the forecast result adjust line update the forecast result
                company = demand.company_id

                if company:
                    for demand in daily_results:
                        daily_demand_id = demand.id
                        finished_product = demand.product_id
                        company_id = demand.company_id.id
                        warehouse_id = demand.warehouse_id.id
                        finished_good_demand = demand.daily_forecast_result
                        date_check = demand.date

                        # # TODO: check this logic
                        # line.write({'direct_demand': finish_good_demand})
                        if finished_product.manufacturing:
                            self._update_indirect_dict(indirect_demand_dict, finished_product,
                                                       finished_good_demand, date_check,
                                                       company_id, warehouse_id, daily_demand_id)

                    if indirect_demand_dict:
                        insert_data = self._get_detail_stock_demand_insert_data(indirect_demand_dict)
                        updated_ids = self._create_update_detail_material_demand(insert_data)
                        # self.env['forecast.item'].create_material_forecast_items(list(indirect_demand_dict.keys()),
                        #                                                          company.id)
                        if updated_ids:
                            self.rounding_forecast_value(updated_ids)
                            self.env['forecast.result.daily'].sudo() \
                                .with_delay(max_retries=12, eta=10) \
                                .update_forecast_result_daily(updated_ids, call_from_engine=True)
                else:
                    UserError('Forecast Result Adjust line %s miss the company information', demand.id)
        except Exception:
            _logger.exception('Function update_forecast_adjust_table have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')

    @api.model
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_forecast_result_daily(self, line_ids, call_from_engine=False):
        """ Inherit the original function and trigger the action update the daily indirect demand for the materials
        after we update their finish goods demand.

        :param list[int] line_ids: forecast result adjust lines id
        :param bool call_from_engine:
        :return:
        """
        try:
            super(InheritForecastResultDaily, self) \
                .update_forecast_result_daily(line_ids, call_from_engine)

            from odoo.tools import config
            allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                 ALLOW_TRIGGER_QUEUE_JOB)

            if not allow_trigger_queue_job:
                self.sudo().update_daily_material_indirect_demand(line_ids)
            else:
                self.sudo().with_delay(max_retries=12).update_daily_material_indirect_demand(line_ids)
        except Exception:
            _logger.exception('Function update_forecast_result_daily have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')
