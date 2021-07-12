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
    def update_records_indirect_forecast_result(self, obj, insert_data, current_time=None):
        """ The function update the indirect demand to database

        :param obj:
        :param list[dict] insert_data:
        :param datetime current_time:
        :return:
        """
        updated_ids = []
        try:
            if insert_data:
                _now = current_time or database_utils.get_db_cur_time(obj.env.cr)

                # append log access fields
                parsed_data = [
                    database_utils.append_log_access_fields_to_data(self, record, current_time=_now)
                    for record in insert_data]

                n_records = len(parsed_data)

                write_time = parsed_data[0]['write_date']

                # get insert fields from the data
                inserted_fields = list(parsed_data[0].keys())
                no_columns = len(inserted_fields)

                sql_query = """
                        INSERT INTO forecast_result_adjust_line
                        (%s)
                        VALUES 
                        (%s)
                        ON CONFLICT (master_product_id, company_id, period_type, start_date)
                        DO UPDATE SET 
                            write_date       = EXCLUDED.write_date,
                            forecast_result  = (CASE WHEN forecast_result_adjust_line.fore_pub_time != EXCLUDED.fore_pub_time 
                                THEN EXCLUDED.forecast_result ELSE EXCLUDED.forecast_result + forecast_result_adjust_line.forecast_result END),
                            adjust_value     = (CASE WHEN forecast_result_adjust_line.fore_pub_time != EXCLUDED.fore_pub_time 
                                THEN EXCLUDED.forecast_result ELSE EXCLUDED.forecast_result + forecast_result_adjust_line.forecast_result END),
                            forecast_line_id = EXCLUDED.forecast_line_id,
                            indirect_forecast = EXCLUDED.indirect_forecast,
                            fore_pub_time    = EXCLUDED.fore_pub_time;
                """ % (
                    ','.join(inserted_fields),
                    ','.join(["%s"] * no_columns)
                )

                sql_params = [get_key_value_in_dict(item, inserted_fields) for item in parsed_data]
                self.env.cr.executemany(sql_query, sql_params)
                self.env.cr.execute("""
                        SELECT id FROM forecast_result_adjust_line WHERE write_date = %s
                """, (write_time, ))
                updated_ids = [item.get('id') for item in self.env.cr.dictfetchall()]

                logging.info("Finish insert %d new indirect demands into the table forecast_result_adjust_line."
                             % n_records)
            else:
                logging.info("Don't have any products should be update the indirect demands.")
        except Exception as e:
            _logger.exception("Error in the function update_records_indirect_forecast_result.", exc_info=True)
            raise e
        return updated_ids

    def update_detail_stock_demand(self, insert_data, current_time=None):
        """ The function update the detail of indirect demand to the table detail_stock_demand

        :param insert_data:
        :type insert_data: list[dict]
        :param current_time:
        :type current_time: datetime
        :return: return to the list of detail_stock_demand id
        :rtype: list[int]
        """
        updated_ids = []
        try:
            if insert_data:
                _now = current_time or database_utils.get_db_cur_time(self.env.cr)

                # append log access fields
                parsed_data = [
                    database_utils.append_log_access_fields_to_data(self, record, current_time=_now)
                    for record in insert_data]

                n_records = len(parsed_data)

                write_time = parsed_data[0]['write_date']

                # get insert fields from the data
                inserted_fields = list(parsed_data[0].keys())
                no_columns = len(inserted_fields)

                sql_query = """
                        INSERT INTO detail_stock_demand
                        (%s)
                        VALUES 
                        (%s)
                        ON CONFLICT (source_line_id, affected_line_id)
                        DO UPDATE SET 
                            no_days_affect      = EXCLUDED.no_days_affect,
                            affect_from         = EXCLUDED.affect_from,
                            affect_to           = EXCLUDED.affect_to,
                            write_date          = EXCLUDED.write_date,
                            write_uid           = EXCLUDED.write_uid;
                """ % (
                    ','.join(inserted_fields),
                    ','.join(["%s"] * no_columns)
                )

                sql_params = [get_key_value_in_dict(item, inserted_fields) for item in parsed_data]
                self.env.cr.executemany(sql_query, sql_params)
                self.env.cr.execute("""
                        SELECT id FROM forecast_result_adjust_line WHERE write_date = %s
                """, (write_time, ))
                updated_ids = [item.get('id') for item in self.env.cr.dictfetchall()]

                logging.info("Finish insert %d new indirect demands into the table detail_stock_demand."
                             % n_records)
            else:
                logging.info("Don't have any forecast item will be updated to the detail stock demands.")
        except Exception as e:
            _logger.exception("Error in the function update_detail_stock_demand.", exc_info=True)
            raise e
        return updated_ids

    ###############################
    # PRIVATE FUNCTIONS
    ###############################
    def _get_period_dict(self, indirect_demand_dict):
        """ Get the dictionary of list of item have same period type from table product_forecast_config

        :param dict indirect_demand_dict: the dictionary contain the indirect demand computed from
        the direct of the finished good demand
        Ex: {
                (product_id, company_id, warehouse_id, line_id, bom_info_id): {
                    date_1: 0,
                    date_2: 0,
                    date_3: 1,
                }
            }
        :return lis
        :return: dictionary of key is the period type and value is the list of item key
        Ex: {
                'weekly': [(pid, cid, wid), ...]
            }
        :rtype: dict
        """
        period_dict = {}
        list_domain_items = []
        keys = list(indirect_demand_dict.keys())
        for key in keys:
            list_domain_items.append(expression.AND([
                [('product_id', '=', key[0])],
                [('company_id', '=', key[1])],
                [('warehouse_id', '=', key[2])]
            ]))
        domain = expression.OR(list_domain_items)
        pfc_ids = self.env['product.forecast.config'].search(domain)
        remain_keys = set(keys)
        for pfc in pfc_ids:
            period_type = pfc.period_type_custom
            items = period_dict.setdefault(period_type, [])
            tuple_key = (pfc.product_id and pfc.product_id.id or False,
                         pfc.company_id and pfc.company_id.id or False,
                         pfc.warehouse_id and pfc.warehouse_id.id or False)
            remain_keys -= {tuple_key}
            items.append(tuple_key)

        if remain_keys:
            items = period_dict.setdefault(PeriodType.DEFAULT_PERIOD_TYPE, [])
            for key in remain_keys:
                items.append(key)
        return period_dict

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
        return pfc_ids

    def _get_detail_stock_demand_insert_data(self, indirect_demand_dict, pub_time):
        """ The function convert the data in variable indirect_demand_dict to the list of dictionary
        that we use to insert to the table forecast_result_adjust_line

        Assumption:
            - all items in indirect_demand_dict have same company_id that the value we push in the param
            get corresponding strategy

        :param dict indirect_demand_dict: the dictionary contain the indirect demand computed from
        the direct of the finished good demand
        Ex: {
                (product_id, company_id, warehouse_id, line_id, bom_info_id): {
                    date_1: 0,
                    date_2: 0,
                    date_3: 1,
                }
            }
        :return list[dict]: the list of dictionary contain data to write to table forecast_result_adjust_line
        Ex: [{
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
            },...]
        """
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
        for period_type, list_items in period_dict.items():

            df_freq_str = df_freq_str_dict[period_type]
            # TODO: here
            item_data = pd.concat([detail_demand_df[item] for item in list_items], axis=1)

            item_data.index = pd.to_datetime(item_data.index)

            # Group by sum for the demand data with the period type
            sum_data = item_data.resample(df_freq_str).sum()
            no_items = sum_data.shape[1]
            sum_data = sum_data.reset_index()
            date_series = pd.Series(sum_data['index'])
            period = date_series.dt.to_period(df_freq_str)

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

    def _convert_to_insert_data(self, indirect_demand_dict, pub_time):
        """

        Assumption:
            - all items in indirect_demand_dict have same company_id that the value we push in the param
            get corresponding strategy

        :param indirect_demand_dict:
        Ex: {
                (product_id, company_id, warehouse_id): {
                    date_1: 0,
                    date_2: 20,
                    date_3: 20,
                }
            }
        :type indirect_demand_dict: dict
        :return list[data]: the list of dictionary contain data to write to table forecast_result_adjust_line
        """
        period_dict = self._get_period_dict(indirect_demand_dict)
        df = pd.DataFrame(indirect_demand_dict)

        df_freq_str_dict = dict([
            (PeriodType.DAILY_TYPE, 'D'),
            (PeriodType.WEEKLY_TYPE, 'W'),
            (PeriodType.MONTHLY_TYPE, 'M'),
            (PeriodType.QUARTERLY_TYPE, 'Q'),
            (PeriodType.YEARLY_TYPE, 'Y')])
        insert_data = []
        for period_type, list_items in period_dict.items():
            df_freq_str = df_freq_str_dict[period_type]
            item_data = df.filter(list_items)
            item_data.index = pd.to_datetime(item_data.index)
            sum_data = item_data.resample(df_freq_str).sum()
            no_items = sum_data.shape[1]
            sum_data = sum_data.reset_index()
            date_series = pd.Series(sum_data['index'])
            period = date_series.dt.to_period(df_freq_str)

            sum_data['period'] = period
            sum_data['start_date'] = period.apply(lambda r: r.start_time)
            sum_data['end_date'] = period.apply(lambda r: r.end_time)
            sum_data.pop('index')
            sum_data_dict = sum_data.to_dict('split')

            columns = sum_data_dict['columns']
            start_date_index = columns.index(('start_date', '', ''))
            end_date_index = columns.index(('end_date', '', ''))

            for row_index, cols_value in enumerate(sum_data_dict.get('data')):
                start_date = cols_value[start_date_index].date()
                end_date = cols_value[end_date_index].date()
                for col_index, value in enumerate(cols_value):
                    if col_index < no_items:
                        key = columns[col_index]
                        product_id = key[0]
                        company_id = key[1]
                        warehouse_id = key[2] or None
                        insert_data.append({
                            'product_id': product_id,
                            'company_id': company_id,
                            'warehouse_id': warehouse_id,
                            'start_date': str(start_date),
                            'end_date': str(end_date),
                            'period_type': period_type,
                            'forecast_result': value,
                            'adjust_value': value,
                            'indirect_forecast': value,
                            'fore_pub_time': str(pub_time),
                        })

        return insert_data

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
        self.env.execute(query, {
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
    def update_material_qty(self, write_time):
        """ Update the Material Demand from the demand of their finished goods after it's updated
        this is assume all lines are updated on write_time have same company

        :param datetime write_time: the write time of the list of forecast result adjust lines data have just updated
        :return None:
        """
        indirect_demand_dict = {}

        # Step 1: get the list of forecast result adjust lines are writen at ``write_time``
        line_ids = self.search([('write_date', '=', write_time)])
        if line_ids:
            line = line_ids[0]
            # The fist line always have the company info and the forecast pub time because this function just triggered
            # right after the forecast result adjust line update the forecast result
            company = line.company_id
            company_id = company.id
            pub_time = line.fore_pub_time

            if company and pub_time:
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
                    updated_ids = self.update_detail_stock_demand(insert_data, write_time)
                    self.env['forecast.item'].create_material_forecast_items(list(indirect_demand_dict.keys()),
                                                                             company.id)
                    if updated_ids:
                        self.rounding_forecast_value(updated_ids)
                        self.env['forecast.result.daily'].sudo() \
                            .with_delay(max_retries=12, eta=10) \
                            .update_forecast_result_daily(updated_ids, company_id, call_from_engine=True)
            else:
                UserError('Forecast Result Adjust line %s miss the company information', line.id)

    @api.model
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_forecast_adjust_line_table(self, created_date, pub_time, **kwargs):
        """ Inherit the original function and trigger the action update the indirect demand for the materials
        after we update their finish goods demand.

        :param created_date:
        :param pub_time:
        :param kwargs:
        :return:
        """
        try:
            update_at = super(InheritForecastResultAdjustLine, self) \
                .update_forecast_adjust_line_table(created_date, pub_time, **kwargs)

            from odoo.tools import config
            allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                 ALLOW_TRIGGER_QUEUE_JOB)

            if not allow_trigger_queue_job:
                self.sudo().update_material_qty(update_at)
            else:
                self.sudo().with_delay(max_retries=12).update_material_qty(update_at)
        except Exception:
            _logger.exception('Function update_forecast_adjust_table have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')
        return update_at

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
