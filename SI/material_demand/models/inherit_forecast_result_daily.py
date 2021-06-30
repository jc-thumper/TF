# -*- coding: utf-8 -*-

import logging
import math

import pandas as pd

from datetime import timedelta

from odoo import models, fields, api

from odoo.exceptions import UserError
from odoo.addons.queue_job.job import job
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.tools.float_utils import float_round

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
                              start_date, end_date, extra_info, line_id):
        """ The function update data for dictionary indirect_demand_dict

        :param dict indirect_demand_dict: the dictionary store the indirect demand of the
        list of products that is the direct or indirect material of current finished good.
        This variable store the daily demand; this dictionary is Empty at the beginning
        Ex: {
                (product_id, company_id, warehouse_id, line_id, bom_info_id): {
                    date_1: 0,
                    date_2: 0,
                    date_3: 1,
                }
            }
        :param ProductProduct finished_id:
        :param finish_good_demand:
        :param datetime.datetime start_date: start date of the range compute the demand of the finished_id
        :param datetime.datetime end_date: end date of the range compute the demand of the finished_id
        :param int line_id: id of forecast result adjust line
        :return: None
        """
        # finding all BoMs this finished good
        bom_info_ids = self.env['product.bom.info']\
            .search([('target_product_id', '=', finished_id.id)])

        for bom_info in bom_info_ids:
            bom_info_id = bom_info.id
            product_unit_qty = bom_info.material_factor
            material_id = bom_info.product_id

            produce_delay = bom_info.produce_delay
            days_gap = int((end_date - start_date).days + 1)

            po_perc = finished_id.po_perc
            manufacturing_demand = finish_good_demand * (1 - po_perc/100.0)

            # The number of Unit of BoMs that we need to make MO
            material_qty_raw = math.ceil(manufacturing_demand / product_unit_qty)

            material_qty = float_round(
                material_qty_raw,
                precision_rounding=material_id.uom_id.rounding,
                rounding_method='UP')

            daily_avg_demand = material_qty / days_gap
            start_point = start_date + timedelta(days=produce_delay)
            end_point = end_date + timedelta(days=produce_delay)

            material_key = (material_id.id,) + extra_info + (line_id, bom_info_id,)
            material_demand_dict = indirect_demand_dict.setdefault(material_key, {})

            while (end_point - start_point).days >= 0:
                demand = material_demand_dict.get(start_point, 0)
                demand_qty = demand + daily_avg_demand
                material_demand_dict[start_point] = demand_qty
                start_point += timedelta(days=1)

    @api.model
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_daily_material_indirect_demand(self, line_ids):
        """ Update the daily Material Indirect Demand from the daily demand of their finished goods after it's updated
        this is assume all lines in have same company

        :param list[int] line_ids:
        :return None:
        """
        try:
            indirect_demand_dict = {}

            # Step 1: get the list of forecast result adjust lines are writen at ``write_time``
            line_ids = self.search([('forecast_adjust_line_id', '=', line_ids)])
            if line_ids:
                line = line_ids[0]
                # The fist line always have the company info and the forecast pub time because
                # this function is just triggered right after the forecast result adjust line update the forecast result
                company_id = line.company_id
                pub_time = line.fore_pub_time

                if company_id and pub_time:
                    for line in line_ids:
                        line_id = line.id
                        product_id = line.product_id
                        finished_good_demand = line.forecast_result
                        start_date = line.start_date
                        end_date = line.end_date

                        # # TODO: check this logic
                        # line.write({'direct_demand': finish_good_demand})
                        if product_id.manufacturing:
                            self._update_indirect_dict(indirect_demand_dict, product_id,
                                                       finished_good_demand, start_date, end_date,
                                                       (line.company_id.id, line.warehouse_id.id), line_id)

                    if indirect_demand_dict:
                        insert_data = self._get_detail_stock_demand_insert_data(indirect_demand_dict, pub_time=pub_time)
                        updated_ids = self.update_detail_stock_demand(insert_data)
                        self.env['forecast.item'].create_material_forecast_items(list(indirect_demand_dict.keys()),
                                                                                 company_id.id)
                        if updated_ids:
                            self.rounding_forecast_value(updated_ids)
                            self.env['forecast.result.daily'].sudo() \
                                .with_delay(max_retries=12, eta=10) \
                                .update_forecast_result_daily(updated_ids, call_from_engine=True)
                else:
                    UserError('Forecast Result Adjust line %s miss the company information', line.id)
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
