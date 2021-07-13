# -*- coding: utf-8 -*-

import logging
import math

import pandas as pd

from datetime import timedelta, datetime

from odoo.addons.si_core.utils import database_utils

from odoo.addons.si_core.utils.request_utils import get_key_value_in_dict
from odoo.addons.forecast_base.utils.config_utils import ALLOW_TRIGGER_QUEUE_JOB

from odoo.addons.queue_job.job import job
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.addons import decimal_precision as dp
from odoo.osv import expression
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.addons.si_core.utils import datetime_utils

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class InheritForecastResultAdjustLine(models.Model):
    _inherit = 'forecast.result.adjust.line'

    ###############################
    # FIELDS
    ###############################
    indirect_forecast = fields.Float(string=_('Indirect Demand Forecast'), store=True,
                                     readonly=True, required=False,
                                     digits=dp.get_precision('Product Unit of Measure'),
                                     help='The total indirect demand that we use this product as a raw material or '
                                          'semi product used to produce other finished products')
    # New
    indirect_demand = fields.Float(string=_('Indirect Actual Demand'), store=True,
                                   readonly=True, required=False,
                                   digits=dp.get_precision('Product Unit of Measure'),
                                   help='The total indirect history demand that we use this product as a raw material'
                                        ' or semi product used to produce other finished products in the Actual')

    stock_demand = fields.Float(string=_('Total Forecast Demand'), readonly=True, required=False,
                                compute='_compute_stock_demand',
                                digits=dp.get_precision('Product Unit of Measure'),
                                help='The total demand of this product (Used to buy or manufacture)')

    ###############################
    # ONCHANGE FUNCTIONS
    ###############################

    ###############################
    # COMPUTED FUNCTIONS
    ###############################
    def _compute_stock_demand(self):
        for line in self:
            line.stock_demand = line.indirect_forecast + line.adjust_value

    ###############################
    # INVERSE FUNCTIONS
    ###############################

    ###############################
    # GENERAL FUNCTIONS
    ###############################

    ###############################
    # PRIVATE FUNCTIONS
    ###############################
    def _get_product_forecast_config_dict(self, tuple_keys):
        """ Get the dictionary of list of item have same period type from table product_forecast_config

        :param list[tuple] tuple_keys: [(product_id, company_id)]
        :return lis
        :return dict[ProductForecastConfig]: Product Forecast Config
        """
        list_domain_items = []
        product_forecast_config_dict = {}
        for key in tuple_keys:
            list_domain_items.append(expression.AND([
                [('product_id', '=', key[0])],
                [('company_id', '=', key[1])],
                [('warehouse_id', '=', key[2])]
            ]))
        domain = expression.OR(list_domain_items)
        pfc_ids = self.env['product.forecast.config'].search(domain)
        for pfc in pfc_ids:
            product_forecast_config_dict[(pfc.product_id.id, pfc.company_id.id, pfc.warehouse_id.id)] = pfc
        return product_forecast_config_dict

    def _compute_indirect_demand_in_range(self, product_id, company_id, warehouse_id, start_date, end_date):
        """ Function compute the indirect demand of an item in a range time

        :param int product_id:
        :param int company_id:
        :param int warehouse_id:
        :param str start_date:
        :param str end_date:
        :return float:
        """
        query = """
                    SELECT sum(indirect_demand) FROM forecast_result_daily frd 
                    WHERE frd.product_id = %(product_id)s 
                        AND frd.company_id = %(company_id)s AND frd.warehouse_id = %(warehouse_id)s 
                        AND frd.date >= %(start_date)s AND frd.date >= %(end_date)s;
        """
        self.env.cr.execute(query, {
            'product_id': product_id,
            'company_id': company_id,
            'warehouse_id': warehouse_id,
            'start_date': start_date,
            'end_date': end_date})
        return self.env.cr.fetchone()[0] or 0.0

    def _update_indirect_dict_from_daily_demand(self, update_ids):
        """

        :param list[int] update_ids:
        :return:
        """
        if update_ids:
            self._cr.execute("""
                    UPDATE forecast_result_adjust_line fral
                    SET indirect_forecast = (SELECT sum(indirect_demand) FROM forecast_result_daily frd 
                    WHERE fral.product_id = frd.product_id 
                        AND fral.company_id = frd.company_id AND fral.warehouse_id = frd.warehouse_id 
                        AND fral.start_date >= frd.date AND fral.end_date <= frd.date) WHERE fral.id IN %s;""",
                             (tuple(update_ids), ))
            self._cr.commit()

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
        bom_info_ids = self.env['product.bom.info'] \
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

    ###############################
    # JOB FUNCTIONS
    ###############################
    @api.model
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_indirect_demand_line(self, daily_demand_ids):
        """
        Step 1: Generate the list of tuple keys from the daily indirect forecast demand
        Step 2: Get Product forecast Config from the list of tuple keys
        Step 3: Loop each daily indirect forecast demand
        Step 3.1: check even if that key have been add to the updated/created list before
        Step 3.2: Find the suitable forecast Result Adjust Line
        Step 3.3: If exist, append the id of that line to the list of lines will be affected
        Step 3.4.1: If it doesn't exist, find the corresponding product forecast config
        Step 3.4.2: compute the line data as a dict and append to the create data
        Step 3.4.3: note that product as compute
        Step 3.5: Update the data to the list of existing lines
        Step 3.6: Create the list of lines
        :return datetime: the create_date/write_date of the created/updated records
        """
        try:
            # Step 1: Generate the list of tuple keys from the daily indirect forecast demand
            frds = self.env['forecast.result.daily'].browse(daily_demand_ids)
            tuple_keys = [(frd.product_id.id, frd.company_id.id, frd.warehouse_id.id) for frd in frds]
            current_time = datetime.now()

            # Step 2: Get Product forecast Config from the list of tuple keys
            product_forecast_config_dict = self._get_product_forecast_config_dict(tuple_keys)

            # Step 3: Loop each daily indirect forecast demand
            create_data = []
            update_ids = []
            checked_line_keys = []
            for frd in frds:
                product_id = frd.product_id.id
                company_id = frd.company_id.id
                warehouse_id = frd.warehouse_id.id
                checking_date = frd.date
                item_key = (product_id, company_id, warehouse_id)
                # Step 3.1: get corresponding product forecast config
                config = product_forecast_config_dict.get(item_key)

                if config:
                    period_type = config.period_type
                    start_date, end_date = datetime_utils.get_start_end_date_value(checking_date, period_type)
                    line_key = item_key + (start_date, end_date)

                    # Step 3.2: check even if that key have been add to the updated/created list before
                    if line_key not in checked_line_keys:
                        # Step 3.3: Find the suitable forecast Result Adjust Line
                        line = self.search([('product_id', '=', product_id), ('company_id', '=', company_id),
                                            ('warehouse_id', '=', warehouse_id),
                                            ('start_date', '=', start_date), ('end_date', '=', end_date)], limit=1)

                        # Step 3.4: If exist, append the id of that line to the list of lines will be affected
                        if line:
                            update_ids.append(line.id)

                        # Step 3.5.1: If it doesn't exist, update the list of create data
                        else:
                            # Step 3.5.2: Compute the indirect demand in the range
                            indirect_forecast = self._compute_indirect_demand_in_range(product_id, company_id,
                                                                                       warehouse_id, start_date,
                                                                                       end_date)

                            # Step 3.5.3: compute the line data as a dict and append to the create data
                            create_data.append({
                                'product_id': product_id,
                                'company_id': company_id,
                                'warehouse_id': warehouse_id,
                                'fore_pub_time': current_time,
                                'period_type': period_type,
                                'start_date': start_date,
                                'end_date': end_date,
                                'indirect_forecast': indirect_forecast
                            })

                        checked_line_keys.append(line_key)

            # Step 3.6: Update the data to the list of existing lines
            self._update_indirect_dict_from_daily_demand(update_ids)

            # Step 3.7: Create the list of lines
            self.create(create_data)

        except Exception:
            _logger.exception('Function update_forecast_adjust_table have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')
