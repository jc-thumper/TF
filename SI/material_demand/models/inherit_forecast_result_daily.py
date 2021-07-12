# -*- coding: utf-8 -*-
import json
import logging

from datetime import datetime, timedelta

from odoo import models, fields, api

from odoo.osv import expression
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

from odoo.addons.queue_job.job import job
from odoo.addons.queue_job.exception import RetryableJobError

from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.addons.si_core.utils.request_utils import get_key_value_in_dict

from odoo.addons.forecast_base.utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB, ALLOW_TRIGGER_QUEUE_JOB

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
    def _update_indirect_demand_dict(self, indirect_demand_dict, finished_product, finish_good_demand,
                                     date_check, company_id, warehouse_id, daily_demand_id):
        """ The function update data for dictionary indirect_demand_dict

        :param dict indirect_demand_dict: the dictionary store the indirect demand of the
        list of products that is the direct or indirect material of current finished good.
        This variable store the daily demand; this dictionary is Empty at the beginning
        Ex: {
                (product_id, company_id, warehouse_id): [
                    {
                        'date': date_1,
                        'daily_demand_id': daily_demand_id1,
                        'indirect_demand': 122.2,
                        'bom_info_id': bom_info_id
                    }, {
                        'date': date_2,
                        'daily_demand_id': daily_demand_id2,
                        'indirect_demand': 221.1,
                        'bom_info_id': bom_info_id2
                    },
                ]
            }
        :param ProductProduct finished_product:
        :param float finish_good_demand:
        :param datetime date_check: the date that is used to compute the demand of the finished_id
        :param int daily_demand_id: id of forecast result adjust line
        :return: None
        """
        # finding all BoMs this finished good
        bom_info_ids = self.env['product.bom.info'] \
            .search([('target_product_id', '=', finished_product.id)])

        for bom_info in bom_info_ids:
            bom_info_id = bom_info.id
            product_unit_qty = bom_info.material_factor
            material = bom_info.product_id

            produce_delay = bom_info.produce_delay

            po_perc = finished_product.po_perc
            manufacturing_demand = finish_good_demand * (1 - po_perc/100.0)

            # The number of Unit of BoMs that we need to make MO
            material_qty_raw = manufacturing_demand / product_unit_qty

            material_qty = float_round(
                material_qty_raw,
                precision_rounding=material.uom_id.rounding,
                rounding_method='UP')

            date_check_point = date_check + timedelta(days=produce_delay)

            material_key = (material.id, company_id, warehouse_id)
            material_demands = indirect_demand_dict.setdefault(material_key, [])
            material_demands.append({
                'date': date_check_point,
                'daily_demand_id': daily_demand_id,
                'indirect_demand': material_qty,
                'bom_info_id': bom_info_id
            })

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
                (product_id, company_id, warehouse_id): [
                    {
                        'date': date_1,
                        'daily_demand_id': daily_demand_id1,
                        'indirect_demand': 122.2,
                        'bom_info_id': bom_info_id
                    }, {
                        'date': date_2,
                        'daily_demand_id': daily_demand_id2,
                        'indirect_demand': 221.1,
                        'bom_info_id': bom_info_id2
                    },
                ]
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
        for keys, indirect_demands in indirect_demand_dict.items():
            product_id = keys[0]
            company_id = keys[1]
            warehouse_id = keys[2]
            key = (product_id, company_id, warehouse_id)

            for demand in indirect_demands:
                date = demand['date']
                indirect_demand = demand['indirect_demand']
                daily_demand_id = demand['daily_demand_id']
                item_key = key + (date,)

                insert_data_item = insert_data_dict.get(item_key, {})
                if not insert_data_item:
                    insert_data_item.update({
                        'product_id': product_id,
                        'company_id': company_id,
                        'warehouse_id': warehouse_id,
                        'date': date,
                        'active': True,
                        'include_indirect_demand': True,
                        'indirect_demand': indirect_demand,
                        'detail_indirect_demand': {
                            daily_demand_id: indirect_demand,
                        }
                    })
                    insert_data.append(insert_data_item)
                else:
                    insert_data_item['indirect_demand'] += indirect_demand
                    detail_demand_dict = insert_data_item['detail_indirect_demand']
                    detail_demand_dict[daily_demand_id] = detail_demand_dict.get(daily_demand_id, 0) + indirect_demand

        for item in insert_data:
            item['detail_indirect_demand'] = json.dumps(item['detail_indirect_demand'])

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
        :return list[int]: return to the list of forecast_result_daily id that have just been updated
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
                            indirect_demand         = (CASE WHEN forecast_result_daily.indirect_demand IS NULL 
                                THEN 0 
                                ELSE forecast_result_daily.indirect_demand END) + EXCLUDED.indirect_demand,
                            detail_indirect_demand  = (CASE WHEN forecast_result_daily.detail_indirect_demand IS NULL 
                                    OR forecast_result_daily.detail_indirect_demand = '' 
                                THEN '{}' 
                                ELSE forecast_result_daily.detail_indirect_demand END)::jsonb || EXCLUDED.detail_indirect_demand::jsonb,
                            active                  = True
                        RETURNING id;
                """ % (
                    ','.join(inserted_fields),
                    ','.join(["%s"] * no_columns)
                )

                for item in insert_data:
                    self.env.cr.execute(sql_query, get_key_value_in_dict(item, inserted_fields))
                    updated_ids.append(self.env.cr.fetchone()[0])

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
    def update_daily_material_indirect_demand(self, fral_ids, company_id):
        """ Update the daily Material Indirect Demand from the daily demand of their finished goods after it's updated
        this is assume all lines in have same company

        :param list[int] fral_ids:
        :param int company_id:
        :return None:
        """
        try:
            indirect_demand_dict = {}

            # Step 1: get the list of forecast result adjust lines are writen at ``write_time``
            daily_results = self.search([('forecast_adjust_line_id', '=', fral_ids), ('company_id', '=', company_id)])
            if daily_results:
                # The fist line always have the company info and the forecast pub time because
                # this function is just triggered right after the forecast result adjust line update the forecast result
                company = self.env['res.company'].browse(company_id)
                updated_ids = []

                if company:
                    for demand in daily_results:
                        finished_product = demand.product_id

                        # # TODO: check this logic
                        # line.write({'direct_demand': finish_good_demand})
                        if finished_product.bom_ids:
                            daily_demand_id = demand.id
                            warehouse_id = demand.warehouse_id.id
                            finished_good_demand = demand.daily_forecast_result
                            date_check = demand.date
                            self._update_indirect_demand_dict(indirect_demand_dict, finished_product,
                                                              finished_good_demand, date_check,
                                                              company_id, warehouse_id, daily_demand_id)

                    if indirect_demand_dict:
                        insert_data = self._get_detail_stock_demand_insert_data(indirect_demand_dict)
                        updated_ids += self._create_update_detail_material_demand(insert_data)

                    if updated_ids:

                        from odoo.tools import config
                        threshold_trigger_queue_job = int(config.get('threshold_to_trigger_queue_job',
                                                                     DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
                        allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                             ALLOW_TRIGGER_QUEUE_JOB)

                        number_of_record = len(updated_ids)

                        if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                            self.env['product.forecast.config'].sudo() \
                                .with_delay(max_retries=12, eta=10) \
                                .generate_forecast_config_from_indirect_demand(updated_ids, company_id)
                        else:
                            self.env['product.forecast.config'].sudo() \
                                .generate_forecast_config_from_indirect_demand(updated_ids, company_id)

                else:
                    UserError('Can not find the Company %s When compute the daily indirect demand', company_id)
        except Exception:
            _logger.exception('Function update_daily_material_indirect_demand have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')

    @api.model
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_forecast_result_daily(self, line_ids, company_id, call_from_engine=False):
        """ Inherit the original function and trigger the action update the daily indirect demand for the materials
        after we update their finish goods demand.

        :param list[int] line_ids: forecast result adjust lines id
        :param int company_id:
        :param bool call_from_engine:
        :return:
        """
        try:
            super(InheritForecastResultDaily, self) \
                .update_forecast_result_daily(line_ids, company_id, call_from_engine)

            from odoo.tools import config
            allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                 ALLOW_TRIGGER_QUEUE_JOB)

            if not allow_trigger_queue_job:
                self.sudo().update_daily_material_indirect_demand(line_ids, company_id)
            else:
                self.sudo().with_delay(max_retries=12).update_daily_material_indirect_demand(line_ids, company_id)
        except Exception:
            _logger.exception('Function update_forecast_result_daily have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')
