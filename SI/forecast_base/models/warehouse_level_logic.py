# -*- coding: utf-8 -*-

import logging
import abc

import pandas as pd
import numpy as np

from psycopg2.extensions import AsIs
from dateutil.relativedelta import relativedelta

from odoo import models, api, fields, _

from odoo.addons.si_core.utils.dataframe_utils import filter_rows_by_tuple
from ..utils.config_utils import ForecastLevelLogicConfig
from ...si_core.utils import database_utils

from .forecast_level_logic import ForecastLevelLogic

_logger = logging.getLogger(__name__)


class InheritForecastLevelStrategy(models.Model):
    _inherit = "forecast.level.strategy"

    ###############################
    # HELPER FUNCTIONS
    ###############################
    def get_object(self):
        """ Function return the Object containing the logic use when switch the forecast level;
        it will return ``None`` if this level don't exist before.

        :return:
        :rtype: Union[None, object]
        """
        self.ensure_one()
        obj = super(InheritForecastLevelStrategy, self)
        if self.name == ForecastLevelLogicConfig.WAREHOUSE_LEVEL:
            obj = WarehouseLevelLogic()
        return obj

    @api.model
    def create_obj(self, forecast_level, **kwargs):
        obj = super(InheritForecastLevelStrategy, self)
        if forecast_level == ForecastLevelLogicConfig.WAREHOUSE_LEVEL:
            obj = WarehouseLevelLogic()
        return obj


class WarehouseLevelLogic(ForecastLevelLogic):
    """
    Interface of method to handle the logic for WAREHOUSE level
    """

    def get_full_keys(self):
        return ['product_id', 'company_id', 'warehouse_id']

    def get_required_fields(self):
        required_fields_for_data = [
            ('product_id', int, None),
            ('company_id', int, None),
            ('warehouse_id', int, None),
            ('lot_stock_id', int, None)
        ]
        return required_fields_for_data

    def get_master_available_qty_dict(self, objs, **kwargs):
        """ Return the master quantity of products dictionary
        :param objs: list of product record set that we want to update
        the product quantity to
        :type objs: Product
        :rtype: None
        """
        objs._compute_quantities()
        res = objs._compute_quantities_dict(objs._context.get('lot_id'), objs._context.get('owner_id'),
                                            objs._context.get('package_id'), objs._context.get('from_date'),
                                            objs._context.get('to_date'))
        master_available_qty_dict = {}
        for product in objs:
            product_id = product.id
            master_available_qty_dict[product_id] = res[product_id]['qty_available']
        return master_available_qty_dict

    def compute_master_product_qty(self, objs, **kwargs):
        """ Compute master quantity of products
        :param objs: list of product record set that we want to update
        the product quantity to
        :type objs: Product
        :rtype: None
        """
        objs._compute_quantities()
        for obj in objs:
            obj.master_available_qty = obj.qty_available
            obj.master_virtual_available = obj.virtual_available
            obj.master_free_qty = max(obj.qty_available - obj.reserved_qty, 0)
            obj.master_incoming_qty = obj.incoming_qty
            obj.master_outgoing_qty = obj.outgoing_qty
            obj.master_reserved_qty = obj.reserved_qty

    def compute_qty_on_hand(self, obj, model_name, **kwargs):
        """
        Compute quantity on hand of products
        """
        records = obj.env[model_name].search([])
        for record in records:
            record.qty_available = record.product_id.qty_available

    def get_product_service_level_infos_by_keys(self, obj, model_name, tuple_keys, tuple_values, **kwargs):
        try:
            sql_query = """
                SELECT
                    infos.product_id, infos.company_id, infos.warehouse_id,
                    sl.name
                FROM product_classification_info infos
                JOIN service_level sl on infos.service_level_id = sl.id
            """
            obj.env.cr.execute(sql_query)
            raw_data = obj.env.cr.dictfetchall()
            df = pd.DataFrame.from_records(raw_data)

            # filter records
            df['is_selected'] = filter_rows_by_tuple(df, list_of_keys=tuple_keys, list_of_values=tuple_values)

            records = df[df['is_selected'] == True].to_dict(orient='records')
            result = {
                (item.get('product_id'),
                 item.get('company_id'),
                 item.get('warehouse_id')): item.get('name') for item in records
            }

            return result
        except Exception as e:
            _logger.exception("An exception occur in get_product_service_level_infos_by_keys", exc_info=True)
            raise e

    def get_product_keys(self, **kwargs):
        """
        :param kwargs:
        :return:
        :rtype: list[str]
        """
        return ['product_id', 'company_id', 'warehouse_id']

    def get_total_demand_inventory(self, obj, model_name, product_ids, current_date, **kwargs):
        result = {}
        try:
            # get future demand
            query_orders = """
                select sm.product_id,
                       sum(sm.product_qty) as order_qty
                from stock_move sm
                join stock_location sl on sm.location_id = sl.id
                where sm.product_id in %s
                    and sm.date >= %s
                    and sm.state in ('confirmed', 'assigned')
                    and sl.usage = 'supplier'
                group by sm.product_id; 
            """
            sql_params = (tuple(product_ids), current_date)
            obj.env.cr.execute(query_orders, sql_params)
            orders = obj.env.cr.dictfetchall()

            # get returned value in the future
            query_returned_values = """
                select sm.product_id,
                       sum(sm.product_qty) as returned_qty
                from stock_move sm
                join stock_location sl on sm.location_dest_id = sl.id
                where sm.product_id in %s
                    and sm.date >= %s
                    and sm.state in ('confirmed', 'assigned')
                    and sl.usage = 'supplier'
                group by sm.product_id; 
            """
            obj.env.cr.execute(query_returned_values, sql_params)
            returned_values = obj.env.cr.dictfetchall()

            if orders:
                df = pd.DataFrame.from_records(orders)
                df['order_qty'] = df['order_qty'].fillna(0)

                if returned_values:
                    returned_value_df = pd.DataFrame.from_records(returned_values)
                    df = df.merge(returned_value_df, how='outer', on='product_id')
                    df = df.fillna(0)
                    df['total_demand'] = df['order_qty'] - df['returned_qty']
                else:
                    df = df.rename(columns={'order_qty': 'total_demand'})

                _logger.info("Data: %s", df.head(n=20))

                records = df[['product_id', 'total_demand']].to_dict('records')
                result = {item.get('product_id'): item.get('total_demand') for item in records}

            return result
        except Exception as e:
            _logger.exception("An exception in get_total_demand_inventory.", exc_info=True)
            raise e

    def get_total_supply_inventory(self, obj, model_name, product_ids, current_date, **kwargs):
        result = {}
        try:
            # get future demand
            query_orders = """
                select sm.product_id,
                       sum(sm.product_qty) as order_qty
                from stock_move sm
                join stock_location sl on sm.location_dest_id = sl.id
                where sm.product_id in %s
                    and sm.date >= %s
                    and sm.state in ('confirmed', 'assigned')
                    and sl.usage = 'customer'
                group by sm.product_id; 
            """
            sql_params = (tuple(product_ids), current_date)
            obj.env.cr.execute(query_orders, sql_params)
            orders = obj.env.cr.dictfetchall()

            # get returned value in the future
            query_returned_values = """
                select sm.product_id,
                       sum(sm.product_qty) as returned_qty
                from stock_move sm
                join stock_location sl on sm.location_id = sl.id
                where sm.product_id in %s
                    and sm.date >= %s
                    and sm.state in ('confirmed', 'assigned')
                    and sl.usage = 'customer'
                group by sm.product_id; 
            """
            obj.env.cr.execute(query_returned_values, sql_params)
            returned_values = obj.env.cr.dictfetchall()
            if orders:
                df = pd.DataFrame.from_records(orders)
                df['order_qty'] = df['order_qty'].fillna(0)
                if returned_values:
                    returned_value_df = pd.DataFrame.from_records(returned_values)
                    df = df.merge(returned_value_df, how='outer', on='product_id')
                    df = df.fillna(0)
                    df['total_supply'] = df['order_qty'] - df['returned_qty']
                else:
                    df = df.rename(columns={'order_qty': 'total_supply'})

                _logger.info("Data: %s", df.head(n=20))

                records = df[['product_id', 'total_supply']].to_dict('records')
                result = {item.get('product_id'): item.get('total_supply') for item in records}

            return result
        except Exception as e:
            _logger.exception("An exception in get_total_supply_inventory.", exc_info=True)
            raise e

    def get_daily_forecasting_value(self, obj, model_name, line_ids, period_type='daily', **kwargs):
        result = []
        try:
            # TODO: check performance of this query
            sql_query = """
                INSERT INTO forecast_result_daily
                    (forecast_adjust_line_id, product_id, warehouse_id, company_id, period_type, active, 
                    date, daily_forecast_result)                
                SELECT adjust.id, adjust.product_id, adjust.warehouse_id, adjust.company_id, result.period_type,
                    TRUE, adjust.start_date, adjust.adjust_value
                FROM (
                    SELECT * 
                    FROM forecast_result_adjust_line fral 
                    WHERE fral.id in %s AND fral.period_type = %s) adjust
                JOIN forecast_result result
                    ON adjust.forecast_line_id = result.id
                JOIN (
                    SELECT config.product_id, config.warehouse_id, config.company_id, g.period_type
                    FROM product_forecast_config config
                    JOIN product_classification_info info ON config.product_clsf_info_id = info.id
                    JOIN forecast_group g ON info.forecast_group_id = g.id) AS product_config
                ON 
                    product_config.product_id = adjust.product_id AND
                    product_config.warehouse_id = adjust.warehouse_id AND
                    product_config.company_id = adjust.company_id AND
                    product_config.period_type = %s
                ON CONFLICT (forecast_adjust_line_id, date) 
                DO UPDATE SET
                    daily_forecast_result = EXCLUDED.daily_forecast_result,
                    period_type = EXCLUDED.period_type
                RETURNING forecast_adjust_line_id;
            """

            sql_params = (tuple(line_ids), period_type, period_type,)

            obj.env.cr.execute(sql_query, sql_params)
            result = [item.get('forecast_adjust_line_id') for item in obj.env.cr.dictfetchall()]
            result = np.unique(result).tolist()
            _logger.info("Record ids inserted/updated success in get_daily_forecasting_value: %s, %s",
                         len(result), result)
            obj.env.cr.commit()
        except Exception as e:
            _logger.exception("Exception in get_daily_forecasting_value: %r" % (e,), exc_info=True)
            result = []
        return result

    def get_weekly_forecasting_value(self, obj, model_name, line_ids, period_type='weekly', **kwargs):
        result = []
        try:
            sql_query = """
                WITH RECURSIVE WeeklyDailyStep (step) AS (
                    VALUES (0)
                    UNION ALL
                    SELECT WeeklyDailyStep.step + 1
                    FROM WeeklyDailyStep
                    WHERE WeeklyDailyStep.step < 6)
                INSERT INTO forecast_result_daily
                    (forecast_adjust_line_id, product_id, warehouse_id, company_id, period_type, active, date, daily_forecast_result)
                SELECT 
                    adjust.id, adjust.product_id, adjust.warehouse_id, adjust.company_id, result.period_type, 
                    TRUE,
                    adjust.start_date + WeeklyDailyStep.step * INTERVAL '1 DAY', SUM(adjust.adjust_value)/7
                FROM (
                    SELECT * 
                    FROM forecast_result_adjust_line fral WHERE fral.id in %s AND fral.period_type = %s) adjust
                JOIN forecast_result result ON adjust.forecast_line_id = result.id
                JOIN (
                    SELECT config.product_id, config.warehouse_id, config.company_id, g.period_type
                    FROM product_forecast_config config
                    JOIN product_classification_info info ON config.product_clsf_info_id = info.id
                    JOIN forecast_group g ON info.forecast_group_id = g.id) AS product_config
                    ON 
                        product_config.product_id = adjust.product_id AND
                        product_config.warehouse_id = adjust.warehouse_id AND
                        product_config.company_id = adjust.company_id AND
                        product_config.period_type = %s
                CROSS JOIN WeeklyDailyStep
                GROUP BY adjust.id, adjust.company_id, adjust.warehouse_id, adjust.product_id, adjust.start_date, 
                    result.period_type, WeeklyDailyStep.step
                ON CONFLICT (forecast_adjust_line_id, date)
                DO UPDATE SET
                    daily_forecast_result = EXCLUDED.daily_forecast_result,
                    period_type = EXCLUDED.period_type
                RETURNING forecast_adjust_line_id;
            """

            sql_params = (tuple(line_ids), period_type, period_type,)

            obj.env.cr.execute(sql_query, sql_params)
            result = [item.get('forecast_adjust_line_id') for item in obj.env.cr.dictfetchall()]
            result = np.unique(result).tolist()
            _logger.info("Record ids inserted/updated success in get_weekly_forecasting_value: %s, %s",
                         len(result), result)
            obj.env.cr.commit()
        except Exception as e:
            _logger.exception("Exception in get_weekly_forecasting_value: %r" % (e,), exc_info=True)
            result = []
        return result

    def create_or_update_records_in_forecast_result_daily(self, obj, model_name, line_ids, **kwargs):
        # some helper functions
        def __compute_mean_forecast_values(series, period_type):
            factors = {
                'weekly': 7,
                'monthly': 30,
                'quarterly': 120
            }
            return series / factors.get(period_type, 1)

        def __convert_to_daily_forecast_values(origin_df):
            splitted_df = origin_df.copy()
            period_type = splitted_df.pop('period_type').unique()[0]
            date_diff = {
                'weekly': {'weeks': 1},
                'monthly': {'months': 1},
                'quarterly': {'months': 3}
            }
            start_dates = splitted_df['start_date']
            min_start_date = start_dates.min()
            max_start_date = start_dates.max() + relativedelta(**date_diff.get(period_type, {}))
            date_ranges = pd.date_range(min_start_date, max_start_date, freq='1D')[:-1]
            new_df = pd.DataFrame({'date': date_ranges})
            splitted_df['adjust_value'] = __compute_mean_forecast_values(splitted_df['adjust_value'], period_type)
            new_df = new_df.merge(splitted_df, how='left', left_on='date', right_on='start_date')
            new_df = new_df.fillna(method='pad')
            # drop rows if we don't have forecast values in this periods
            new_df = new_df.dropna(subset=['adjust_value'])
            new_df['period_type'] = period_type
            return new_df

        def __get_product_forecast_config_data(obj):
            sql_query = """
                SELECT config.product_id, config.warehouse_id, config.company_id, g.period_type
                FROM product_forecast_config config
                JOIN product_classification_info info ON config.product_clsf_info_id = info.id
                JOIN forecast_group g ON info.forecast_group_id = g.id;
            """

            obj.env.cr.execute(sql_query)
            records = obj.env.cr.dictfetchall()
            return pd.DataFrame.from_records(records)

        def __get_forecast_result_data(obj, line_ids):
            sql_query = """
                SELECT 
                    fral.id, fral.product_id, fral.warehouse_id, fral.company_id, fral.period_type,
                    fral.start_date, fral.adjust_value
                FROM forecast_result_adjust_line fral 
                WHERE fral.id in %s;
            """
            obj.env.cr.execute(sql_query, (tuple(line_ids),))
            records = obj.env.cr.dictfetchall()
            return pd.DataFrame.from_records(records)

        def __get_records_in_forecast_result_daily(obj):
            sql_query = """
                SELECT forecast_adjust_line_id, date
                FROM forecast_result_daily;
            """
            obj.env.cr.execute(sql_query)
            records = obj.env.cr.dictfetchall()
            return pd.DataFrame.from_records(records)

        def __create_records_in_forecast_result_daily(obj, inserted_records):
            sql_query = """
                INSERT INTO forecast_result_daily
                (forecast_adjust_line_id, product_id, warehouse_id, company_id, period_type, active, 
                date, daily_forecast_result)
                VALUES (
                    %(forecast_adjust_line_id)s, %(product_id)s, %(warehouse_id)s, 
                    %(company_id)s, %(period_type)s, %(active)s, %(date)s, %(daily_forecast_result)s);
            """
            obj.env.cr.executemany(sql_query, inserted_records)
            obj.env.cr.commit()

        def __update_records_in_forecast_result_daily(obj, updated_records):
            sql_query = """
                UPDATE forecast_result_daily
                SET 
                    daily_forecast_result = %(daily_forecast_result)s,
                    period_type = %(period_type)s
                WHERE forecast_adjust_line_id = %(forecast_adjust_line_id)s AND date = %(date)s;
            """
            obj.env.cr.executemany(sql_query, updated_records)
            obj.env.cr.commit()

        try:
            # get product forecast config data
            product_config_df = __get_product_forecast_config_data(obj=obj)

            # get forecast result data
            forecast_result_df = __get_forecast_result_data(obj=obj, line_ids=line_ids)
            forecast_result_df['start_date'] = pd.to_datetime(forecast_result_df['start_date'])

            # get existing records in forecast result daily
            forecast_result_daily_df = __get_records_in_forecast_result_daily(obj=obj)
            if forecast_result_daily_df.empty is False:
                forecast_result_daily_df['date'] = pd.to_datetime(forecast_result_daily_df['date'])
                forecast_result_daily_df['is_existing'] = True

            # convert to daily forecast value
            daily_forecast_df = forecast_result_df.groupby(
                ['period_type', 'product_id', 'warehouse_id', 'company_id'],
                as_index=False).apply(
                lambda splitted_df: __convert_to_daily_forecast_values(splitted_df))

            # add some columns
            daily_forecast_df['active'] = True

            # rename some columns
            daily_forecast_df = daily_forecast_df.rename(columns={
                'id': 'forecast_adjust_line_id',
                'adjust_value': 'daily_forecast_result'
            })

            selected_cols = [
                'forecast_adjust_line_id', 'product_id', 'warehouse_id', 'company_id', 'active',
                'date', 'daily_forecast_result', 'period_type'
            ]
            daily_forecast_df = daily_forecast_df[selected_cols]

            if forecast_result_daily_df.empty is False:
                result = daily_forecast_df.merge(forecast_result_daily_df, how='left',
                                                 left_on=['forecast_adjust_line_id', 'date'],
                                                 right_on=['forecast_adjust_line_id', 'date'])
                result['is_existing'] = result['is_existing'].fillna(False)
            else:
                result = daily_forecast_df.copy()
                result['is_existing'] = False

            # cast type of ID columns to integer
            result = result.astype({
                'forecast_adjust_line_id': 'int32',
                'product_id': 'int32',
                'warehouse_id': 'int32',
                'company_id': 'int32'
            })

            # convert datetime column to string
            result['date'] = result['date'].apply(lambda row: row.strftime('%Y-%m-%d'))

            # filter records to insert/update in database
            inserted_records = result[result['is_existing'] == False][selected_cols].to_dict(orient='records')
            updated_records = result[result['is_existing'] == True][selected_cols].to_dict(orient='records')

            _logger.info("Insert %s records in forecast_result_daily: %s", len(inserted_records), inserted_records[:1])
            _logger.info("Update %s records in forecast_result_daily: %s", len(updated_records), updated_records[:1])

            __create_records_in_forecast_result_daily(obj=obj, inserted_records=inserted_records)
            __update_records_in_forecast_result_daily(obj=obj, updated_records=updated_records)

        except Exception as e:
            _logger.exception("Exception in get_weekly_forecasting_value: %r" % (e,), exc_info=True)

    def get_sold_qty_of_products(self, obj, model_name, period_type='MONTH', period_number=-12, **kwargs):
        records = []
        try:
            sql_query = """
                SELECT 
                    sol.company_id, o.warehouse_id, sol.product_id, 
                    SUM(product_uom_qty) as sold_qty_last_12months
                FROM sale_order_line AS sol
                JOIN sale_order o ON sol.order_id = o.id                
                WHERE 
                    o.state in ('sale', 'confirm') AND 
                    o.confirmation_date >= (NOW() + INTERVAL %s) AND
                    o.confirmation_date <= NOW()
                GROUP BY sol.company_id, o.warehouse_id, sol.product_id;                
            """
            query_params = [str(period_number) + " " + period_type]
            obj.env.cr.execute(sql_query, query_params)
            records = obj.env.cr.dictfetchall()
            return records
        except Exception as e:
            _logger.exception("An exception in get_sold_qty_of_products: %r" % (e,), exc_info=True)
            raise

    def get_conflict_fields_for_rrwf_tracker(self, **kwargs):
        # we need to create UNIQUE INDEX for the table Reordering rule with forecast tracker before
        return ['product_id', 'company_id', 'warehouse_id', 'create_time']

    def create_product_info_df_to_compute_under_overstock(self, obj, model_name, **kwargs):
        df = pd.DataFrame()
        try:
            sql_query = """
                SELECT forecast_result.product_id, forecast_result.company_id, forecast_result.warehouse_id
                FROM forecast_result
                JOIN (
                    SELECT company_id, MAX(pub_time) as max_pub_time
                    FROM forecast_result
                    GROUP BY company_id) temp
                    ON temp.company_id = forecast_result.company_id AND forecast_result.pub_time = temp.max_pub_time
                WHERE forecast_result.warehouse_id IS NOT NULL
                    AND forecast_result.company_id IS NOT NULL
                GROUP BY forecast_result.product_id, forecast_result.company_id, forecast_result.warehouse_id;                
            """
            sql_params = ()
            obj.env.cr.execute(sql_query, sql_params)
            records = obj.env.cr.dictfetchall()
            if records:
                df = df.from_records(records)

            return df
        except Exception as e:
            _logger.exception("An execption in create_product_info_df_to_compute_under_overstock")
            raise e

    def get_demand_of_products(self, obj, model_name, period_type='MONTH', period_number=-6, **kwargs):
        records = []
        try:
            sql_query = """
                SELECT stock_move.company_id, stock_move.warehouse_id, stock_move.product_id,
                       SUM(stock_move.product_qty * stock_move.price_unit) as demand
                FROM stock_move
                JOIN stock_location ON stock_move.location_id = stock_location.id
                WHERE stock_move.state = 'done' AND
                    stock_location.usage = 'supplier' AND
                    stock_move.date <= NOW() AND
                    stock_move.date >= NOW() + INTERVAL %s
                GROUP BY stock_move.company_id, stock_move.warehouse_id, stock_move.product_id;              
            """
            query_param = (str(period_number) + " " + period_type)
            obj.env.cr.execute(sql_query, query_param)
            records = obj.env.cr.dictfetchall()
            return records
        except Exception as e:
            _logger.exception("An exception in get_demand_of_products: %r" % (e,), exc_info=True)
            raise

    def get_procurement_cycle_of_products(self, obj, model_name, **kwargs):
        records = None
        try:
            sql_query = """
                SELECT config.company_id, config.warehouse_id, config.product_id, 
                    config.procurement_cycle 
                FROM product_forecast_config config
                WHERE config.active = TRUE;
            """
            obj.env.cr.execute(sql_query)
            records = obj.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("An exception in get_procurement_cycle_of_products: %r" % (e,), exc_info=True)
            raise
        return records

    def get_min_max_order_qty(self, obj, model_name, **kwargs):
        records = None
        try:
            sql_query = """
                SELECT 
                    orderpoint.company_id, 
                    orderpoint.warehouse_id, 
                    orderpoint.product_id,
                    product_min_qty as min_order_qty,
                    product_max_qty as max_order_qty
                FROM stock_warehouse_orderpoint orderpoint
                WHERE orderpoint.active = TRUE;
            """
            obj.env.cr.execute(sql_query)
            records = obj.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("An exception in get_min_max_order_qty: %r" % (e,), exc_info=True)
            raise
        return records

    def get_total_si_forecast_of_products(self, obj, model_name, product_ids=None, current_time=None, **kwargs):
        records = []
        try:
            # get all records in the ``product_ids``
            sql_query = """
                SELECT 
                    result.product_id, result.warehouse_id, result.company_id,
                    result.daily_forecast_result, result.date
                FROM forecast_result_daily result
                WHERE result.date >= %s
            """
            if current_time is None:
                sql_params = [AsIs('NOW()')]
            else:
                sql_params = [current_time]

            if product_ids:
                sql_query += " AND result.product_id IN %s"
                sql_params += [tuple(product_ids)]

            sql_query += ";"

            obj.env.cr.execute(sql_query, sql_params)
            records = obj.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("An exception in get_total_si_forecast_of_products: %r" % (e,), exc_info=True)
            raise
        return records

    def get_conflict_fields_for_uo_stock_tracker(self, **kwargs):
        return ['product_id', 'company_id', 'warehouse_id', 'create_time']

    def create_initial_records_for_rrwf(self, obj, model_name, **kwargs):
        # sync data in table RRwF with RR table, which contain data of reordering rules,
        # each products just have a row in reordering rules with forecast table
        RRwF_model = obj.env['reordering.rules.with.forecast']
        count = 0
        rules = obj.env['stock.warehouse.orderpoint'].sudo().search([])
        rule_records = []
        for rule in rules:
            record = RRwF_model.search([
                ('product_id', '=', rule.product_id.id),
                ('company_id', '=', rule.company_id.id),
                ('warehouse_id', '=', rule.warehouse_id.id),
                ('location_id', '=', rule.location_id.id)
            ])
            # just products have not had in RRwF table can create new record
            if not record:
                values = {
                    'product_id': rule.product_id.id,
                    'company_id': rule.company_id.id,
                    'warehouse_id': rule.warehouse_id.id,
                    'location_id': rule.location_id.id,
                    'orderpoint_id': rule.id,
                }
                count += 1
                rule_records.append(values)

        RRwF_model.create(rule_records)

        # sync data in table RRwF with FD table, which contain forecast data
        forecasts = obj.env['forecast.result.adjust'].sudo().search([])
        forecasted_product_records = []
        for forecast in forecasts:
            if forecast.has_forecasted:
                product_id = forecast.product_id.id
                company_id = forecast.company_id.id
                warehouse_id = forecast.warehouse_id.id
                location_id = forecast.lot_stock_id.id \
                    if forecast.lot_stock_id \
                    else forecast.warehouse_id.lot_stock_id.id
                record = RRwF_model.search([
                    ('product_id', '=', product_id),
                    ('company_id', '=', company_id),
                    ('warehouse_id', '=', warehouse_id),
                    ('location_id', '=', location_id)
                ])
                # create new record if that product have existed, and update old record in another case
                if not record:
                    values = {
                        'product_id': product_id,
                        'company_id': company_id,
                        'warehouse_id': warehouse_id,
                        'location_id': location_id
                    }
                    count += 1
                    forecasted_product_records.append(values)

        # create multi records
        _logger.info("Create multi record in RRwF for warehouse: %s", len(forecasted_product_records))
        RRwF_model.create(forecasted_product_records)

    def get_product_infos_for_rrwf(self, record, **kwargs):
        """
        :param record: ReorderingRulesWithForecast
        :param kwargs:
        :return:
        :rtype: dict
        """
        result = {}
        if record:
            result = {
                'product_id': record.product_id.id or None,
                'company_id': record.company_id.id or None,
                'warehouse_id': record.warehouse_id.id or None
            }

        return result

    def get_products_info_dict(self, obj, product_ids, **kwargs):
        """ Function return the product information for reordering rule with forecast record
        :param obj:
        :param product_ids: list[int]
        :param kwargs:
        :return:
        :rtype: dict
        """
        result = {}
        for product_id in product_ids:
            result.update({product_id: {'product_id': product_id}})

        return result

    def set_total_si_forecast_of_products(self, obj, model, period_type='procurement_cycle', **kwargs):
        try:
            sql_query = """
                INSERT INTO under_over_stock_report_line
                    (company_id, warehouse_id, product_id, %s)
                SELECT analysis.company_id, analysis.warehouse_id, analysis.product_id,
                    (SELECT SUM(result.daily_forecast_result) AS total_forecast
                    FROM forecast_result_daily result
                    WHERE result.date >= NOW()
                        AND result.date <= (NOW() + (analysis.lead_time + analysis.%s) * INTERVAL '1 DAY')
                        AND result.product_id = analysis.product_id
                        AND result.warehouse_id = analysis.warehouse_id
                        AND result.company_id = analysis.company_id) as total_forecast
                FROM under_over_stock_report_line analysis
                ON CONFLICT (company_id, warehouse_id, product_id)
                DO UPDATE SET %s = EXCLUDED.%s;
            """
            if period_type == 'procurement_cycle':
                field_name = 'total_forecast_in_planning_period'
                sql_params = [AsIs(field_name), AsIs(period_type), AsIs(field_name), AsIs(field_name)]
            elif period_type == 'days_of_stock':
                field_name = 'total_forecast_in_days_of_stock'
                sql_params = [AsIs(field_name), AsIs(period_type), AsIs(field_name), AsIs(field_name)]

            obj.env.cr.execute(sql_query, sql_params)
            obj.env.cr.commit()
        except Exception as e:
            _logger.exception('An exception in set_total_si_forecast_of_products', exc_info=True)
            raise

    def get_conflict_fields_for_demand_classification_result(self, **kwargs):
        return ['product_id', 'company_id', 'warehouse_id', 'pub_time']

    def get_latest_records_dict_for_demand_classification_result(self, obj, model, created_date, **kwargs):
        data_dict = []
        try:
            sql_query = """
                    select
                        product_id, company_id, warehouse_id, demand_clsf_id, pub_time as demand_clsf_pub_time
                    from demand_classification_result
                    where create_date = %s;
                """
            sql_param = (created_date,)
            obj.env.cr.execute(sql_query, sql_param)
            data_dict = obj.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("Error in the function get_latest_records_dict_for_demand_classification_result.",
                              exc_info=True)
            raise e
        return data_dict

    def get_conflict_fields_for_service_level_result(self, **kwargs):
        return ['product_id', 'company_id', 'warehouse_id', 'pub_time']

    def get_latest_records_dict_for_service_level_result(self, obj, model, created_date, **kwargs):
        data_dict = []
        try:
            sql_query = """
                SELECT product_id,
                       company_id,
                       warehouse_id,
                       service_level_id,
                       pub_time AS service_level_pub_time
                FROM service_level_result
                WHERE create_date = %s;
            """
            sql_param = (created_date,)
            obj.env.cr.execute(sql_query, sql_param)
            data_dict = obj.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("Error in the function get_latest_records_dict_for_service_level_result", exc_info=True)
            raise e
        return data_dict

    def update_product_clsf_info_from_demand_classification_result(self, obj, model, **kwargs):
        try:
            sql_query = """
                insert into product_classification_info
                    (product_id, company_id, warehouse_id, demand_clsf_id, demand_clsf_pub_time)
                select product_id, company_id, warehouse_id, demand_clsf_id, pub_time
                from demand_classification_result
                where create_date = %s
                on conflict (product_id, company_id, warehouse_id) do update
                set demand_clsf_id = excluded.demand_clsf_id, demand_clsf_pub_time = excluded.demand_clsf_pub_time
                returning id;
            """
            sql_param = (kwargs.get('created_date'))
            obj.env.cr.execute(sql_query, sql_param)
            updated_ids = [item.get('id') for item in obj.env.cr.dictfetchall()]
            return updated_ids
        except Exception as e:
            _logger.exception("Error in the function update_product_clsf_info_from_demand_classification_result.",
                              exc_info=True)
            raise e

    def update_product_clsf_info_from_service_level_result(self, obj, model, **kwargs):
        try:
            sql_query = """
                insert into product_classification_info
                    (product_id, company_id, warehouse_id, service_level_id, service_level_pub_time)
                select product_id, company_id, warehouse_id, service_level_id, pub_time
                from service_level_result
                where create_date = %s
                on conflict (product_id, company_id, warehouse_id) do update
                set service_level_id = excluded.service_level_id, service_level_pub_time = excluded.service_level_pub_time
                returning id;
            """
            sql_param = (kwargs.get('created_date'))
            obj.env.cr.execute(sql_query, sql_param)
            updated_ids = [item.get('id') for item in obj.env.cr.dictfetchall()]
            return updated_ids
        except Exception as e:
            _logger.exception("Error in the function update_product_clsf_info_from_service_level_result.",
                              exc_info=True)
            raise e

    def get_conflict_fields_for_summarize_rec_result(self, **kwargs):
        return ['product_id', 'company_id', 'warehouse_id', 'pub_time']

    def get_latest_records_dict_for_summarize_rec_result(self, obj, model, created_date, **kwargs):
        data_dict = []
        try:
            sql_query = """
                select
                    product_id, company_id, warehouse_id, start_date, end_date, period_type, id as summ_rec_id,
                    summarize_value, no_picks, picks_with_discount, demand_with_discount, avg_discount_perc
                from summarize_rec_result;
                where create_date = %s;
            """
            sql_param = (created_date,)
            obj.env.cr.execute(sql_query, sql_param)
            data_dict = obj.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("Error in the function get_latest_records_dict_for_summarize_rec_result.", exc_info=True)
            raise e
        return data_dict

    def update_records_for_summarize_data_line(self, obj, model, created_date, **kwargs):
        updated_ids = []
        try:
            if created_date:
                sql_query = """
                    INSERT INTO summarize_data_line
                    (product_id, company_id, warehouse_id, start_date, end_date, period_type, summ_rec_id, 
                    summarize_value, no_picks, picks_with_discount, demand_with_discount, avg_discount_perc)
                    SELECT
                        product_id, company_id, warehouse_id, start_date, end_date, period_type, id as summ_rec_id,
                        summarize_value, no_picks, picks_with_discount, demand_with_discount, avg_discount_perc
                    FROM summarize_rec_result
                    WHERE create_date = %s
                    ON CONFLICT (product_id, company_id, warehouse_id, start_date, period_type)
                    DO UPDATE SET                         
                        write_date = now() at time zone 'UTC', 
                        summ_rec_id = EXCLUDED.summ_rec_id,
                        summarize_value = EXCLUDED.summarize_value,
                        no_picks = EXCLUDED.no_picks,
                        picks_with_discount = EXCLUDED.picks_with_discount,
                        demand_with_discount = EXCLUDED.demand_with_discount,
                        avg_discount_perc = EXCLUDED.avg_discount_perc    
                    RETURNING id;
                """
                sql_param = (created_date,)
                obj.env.cr.execute(sql_query, sql_param)
                updated_ids = [item.get('id') for item in obj.env.cr.dictfetchall()]
        except Exception as e:
            _logger.exception("Error in the function update_records_for_summarize_data_line.", exc_info=True)
            raise e
        return updated_ids

    def get_conflict_fields_for_forecast_result(self, **kwargs):
        return ['product_id', 'company_id', 'warehouse_id', 'pub_time', 'start_date', 'period_type']

    def update_records_for_forecast_result_adjust_line(self, obj, model, created_date, **kwargs):
        """ Function create/update table forecast_result_adjust_line from table forecast_result data which are
        created at ``create_date``. This logic apply for warehouse level
        :param obj:
        :param model:
        :param created_date:
        :param kwargs:
        :return:
        :rtype: list[int]
        """
        updated_ids = []
        try:
            _now = kwargs.get('current_time', database_utils.get_db_cur_time(obj.env.cr))
            if created_date:
                sql_query = """
                    INSERT INTO forecast_result_adjust_line
                    (product_id, company_id, warehouse_id, start_date, end_date, period_type, forecast_result, 
                    adjust_value, forecast_line_id, fore_pub_time, create_uid, create_date, write_uid, write_date)
                    SELECT fr.product_id,
                           fr.company_id,
                           fr.warehouse_id,
                           fr.start_date,
                           fr.end_date,
                           fr.period_type,
                           (CASE WHEN fr.forecast_result < 0 THEN 0 ELSE fr.forecast_result END),
                           (CASE WHEN fr.forecast_result < 0 THEN 0 ELSE fr.forecast_result END),
                           fr.id as forecast_line_id,
                           fr.pub_time as fore_pub_time,
                           fr.create_uid as create_uid,
                           %(now)s as create_date,
                           fr.write_uid as write_uid,
                           %(now)s as write_date
                    FROM (SELECT * FROM forecast_result WHERE create_date = %(created_date)s) AS fr
                      LEFT OUTER JOIN (
                          SELECT *
                          FROM forecast_result_adjust_line
                          WHERE start_date >= %(now)s
                             OR (end_date >= %(now)s AND start_date <= %(now)s)) AS fral
                        ON 
                          fr.product_id IS NOT DISTINCT FROM fral.product_id AND
                          fr.warehouse_id IS NOT DISTINCT FROM fral.warehouse_id AND
                          fr.company_id IS NOT DISTINCT FROM fral.company_id AND
                          fr.start_date = fral.start_date
                    WHERE fr.id IS NOT NULL
                    ON CONFLICT (product_id, company_id, warehouse_id, period_type, start_date)
                    DO UPDATE SET 
                        write_date       = EXCLUDED.write_date,
                        forecast_result  = (CASE WHEN forecast_result_adjust_line.fore_pub_time != EXCLUDED.fore_pub_time 
                        THEN EXCLUDED.forecast_result ELSE EXCLUDED.forecast_result + forecast_result_adjust_line.forecast_result END),
                        adjust_value     = (CASE WHEN forecast_result_adjust_line.fore_pub_time != EXCLUDED.fore_pub_time 
                        THEN EXCLUDED.forecast_result ELSE EXCLUDED.forecast_result + forecast_result_adjust_line.forecast_result END),
                        forecast_line_id = EXCLUDED.forecast_line_id,
                        fore_pub_time    = EXCLUDED.fore_pub_time;
                """
                sql_param = {'created_date': created_date, 'now': _now}
                obj.env.cr.execute(sql_query, sql_param)
                obj.env.cr.commit()

                # get updated row id in forecast_result_adjust_line
                updated_ids_sql_query = """
                    SELECT
                        id
                    FROM forecast_result_adjust_line
                    WHERE forecast_line_id IN (SELECT id FROM forecast_result WHERE create_date = %s);
                """
                obj.env.cr.execute(updated_ids_sql_query, (created_date,))
                updated_ids = [item.get('id') for item in obj.env.cr.dictfetchall()]

        except Exception as e:
            _logger.exception("Error in the function update_records_for_summarize_data_line.", exc_info=True)
            raise e
        return updated_ids

    def update_latest_records_for_uo_stock(self, obj, model, created_date, **kwargs):
        try:
            # get lasted records
            latest_record_ids = obj.get_latest_records(created_date=created_date)
            _logger.info("Update records with IDs: %s", latest_record_ids)
            sql_query = """
                DELETE FROM under_over_stock_report_line;
                INSERT INTO under_over_stock_report_line (
                    tracker_id,
                    product_id,
                    company_id,
                    warehouse_id,
                    state,
                    days_of_stock,
                    days_of_stock_out_risk,
                    days_of_over_stock,
                    potential_value_loss,
                    lead_time,
                    min_order_qty,
                    max_order_qty,
                    total_forecast_in_planning_period,
                    total_forecast_in_days_of_stock,
                    procurement_cycle,
                    odoo_forecasted_on_hand,
                    sale_price,
                    standard_price,
                    demand,
                    create_time,
                    pub_time,
                    active,
                    create_uid, create_date, write_uid, write_date
                )
                SELECT 
                    id,
                    product_id,
                    company_id,
                    warehouse_id,
                    state,
                    days_of_stock,
                    days_of_stock_out_risk,
                    days_of_over_stock,
                    potential_value_loss,
                    lead_time,
                    min_order_qty,
                    max_order_qty,
                    total_forecast_in_planning_period,
                    total_forecast_in_days_of_stock,
                    procurement_cycle,
                    odoo_forecasted_on_hand,
                    sale_price,
                    standard_price,
                    demand,
                    create_time,
                    pub_time,
                    active,
                    create_uid, create_date, write_uid, write_date
                FROM under_over_stock_report_tracker tracker
                WHERE tracker.id IN %s;
            """
            sql_params = (tuple(latest_record_ids),)
            obj.env.cr.execute(sql_query, sql_params)
        except Exception:
            _logger.exception("Error in the function update_latest_records.", exc_info=True)
            raise

    def get_forecast_demand_values_for_investment_report(self, obj, model, product_ids, warehouse_ids, company_id,
                                                         from_start_date, to_start_date, invest_type, **kwargs):
        try:
            sql_query = """
                SELECT
                    product_id, warehouse_id, company_id, 
                    start_date AS from_date, 
                    end_date AS to_date,
                    COALESCE(adjust_value, 0) AS forecasted_demand 
                FROM forecast_result_adjust_line
                WHERE period_type = %s AND start_date >= %s AND start_date <= %s AND company_id = %s
                AND product_id IN %s AND warehouse_id IN %s;
            """
            sql_params = (invest_type, from_start_date, to_start_date, company_id, tuple(product_ids),
                          tuple(warehouse_ids))
            obj.env.cr.execute(sql_query, sql_params)
            result = obj.env.cr.dictfetchall()
            return result
        except Exception as e:
            _logger.exception("An exception in _search_forecast_demand_values_for_investment_report", exc_info=True)
            raise e

    def get_grouped_key_for_investment_report(self):
        return ['product_id', 'warehouse_id']

    ####################################
    # Product Age Report API
    ####################################

    def get_conflict_fields_for_product_age_tracker(self, **kwargs):
        """
        List of fields use to update values in ON DUPLICATE KEY command
        """
        return ['product_id', 'company_id', 'warehouse_id', 'lot_stock_id',
                'order_ref', 'order_finished_date', 'create_time']

    def get_stock_on_hand_for_product_age_report(self, obj, model, **kwargs):
        """
        Get stock on hand of each product in each warehouse
        """
        result = []
        try:
            sql_query = """
                SELECT
                  quant.product_id, quant.company_id, s2.id AS warehouse_id,
                  quant.quantity AS stock_on_hand
                FROM stock_quant quant
                JOIN stock_location l ON quant.location_id = l.id
                JOIN stock_warehouse s2 ON l.id = s2.lot_stock_id;
            """

            obj.env.cr.execute(sql_query)
            result = obj.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("An exception in get_stock_on_hand: %r" % (e,), exc_info=True)
            raise
        return result

    def update_latest_records_for_product_age(self, obj, model, created_date, **kwargs):
        try:
            # get lasted records
            latest_record_ids = obj.get_latest_records(created_date=created_date)
            _logger.info("Update records with IDs: %s", latest_record_ids)
            sql_query = """
                DELETE FROM product_age;
                INSERT INTO product_age (
                    tracker_id,
                    product_id,
                    company_id,
                    warehouse_id,
                    lot_stock_id,
                    order_ref,
                    order_finished_date,
                    stock_on_hand,
                    order_amount,
                    order_quantity,
                    po_age,
                    unsold_qty,
                    unsold_value,
                    create_time,
                    pub_time,
                    create_uid, create_date, write_uid, write_date
                )
                SELECT 
                    id,
                    product_id,
                    company_id,
                    warehouse_id,
                    lot_stock_id,
                    order_ref,
                    order_finished_date,
                    stock_on_hand,
                    order_amount,
                    order_quantity,
                    po_age,
                    unsold_qty,
                    unsold_value,
                    create_time,
                    pub_time,
                    create_uid, create_date, write_uid, write_date
                FROM product_age_tracker tracker
                WHERE tracker.id IN %s;
            """
            sql_params = (tuple(latest_record_ids),)
            obj.env.cr.execute(sql_query, sql_params)
        except Exception:
            _logger.exception("Error in the function update_latest_records.", exc_info=True)
            raise

    def get_po_lines_in_range_for_product_age_report(self, obj, model, company_id, product_ids, start_date=None,
                                                     end_date=None,
                                                     **kwargs):
        po_lines = []
        if product_ids:
            try:
                # NOTE: one Purchase Order Line can have multiple lines for the same product
                query = """
                    SELECT
                           pol.product_id, pol.company_id, spt.warehouse_id, 
                           sum(pol.product_qty) as order_quantity,
                           concat_ws('/', 'PO', pol.order_id) as order_ref, 
                           pol.date_planned as order_finished_date,
                           sum(pol.price_subtotal) as order_amount
                    FROM purchase_order_line pol
                    LEFT JOIN purchase_order po ON pol.order_id = po.id
                    LEFT JOIN stock_picking_type spt ON po.picking_type_id = spt.id
                    WHERE 
                        po.state IN ('done', 'purchase') AND 
                        spt.code = 'incoming' AND 
                        pol.product_id IN %s AND
                        pol.company_id = %s
                    GROUP BY pol.product_id, pol.company_id, spt.warehouse_id, pol.order_id, pol.date_planned
                    ORDER BY pol.date_planned;
                """

                query_params = (tuple(product_ids), company_id,)

                obj.env.cr.execute(query, query_params)
                po_lines = obj.env.cr.dictfetchall()
            except Exception:
                _logger.exception("Error in the function get_po_lines_in_range_for_product_age_report.", exc_info=True)
                raise

        return po_lines

    def get_on_order_values_for_heavy_stock_items(self, obj, model, company_id, product_ids, **kwargs):
        """
        Get purchased qty of a products in the state Purchased
        """
        result = {}

        # filter Purchase Order Line
        orders = obj.env['purchase.order.line'].sudo().search([
            ('company_id', '=', company_id),
            ('product_id', 'in', product_ids),
            ('state', '=', 'purchase')])

        # compute the "on order" value
        for order in orders:
            warehouse_id = order.order_id.picking_type_id.warehouse_id.id or False
            product_id = order.product_id.id
            data_key = str((product_id, warehouse_id))
            # set default values
            result.setdefault(data_key, {
                'on_order_qty': 0
            })
            result[data_key]['on_order_qty'] += order.product_qty

        return result

    def get_mo_lines_in_range_for_product_age_report(self, obj, model, company_id, product_ids, start_date=None,
                                                     end_date=None, **kwargs):
        mo_lines = []
        return mo_lines

    @abc.abstractmethod
    def get_inventory_adjustment_lines_for_product_age_report(self, obj, model, company_id, product_ids, **kwargs):
        inventory_adjust_lines = []
        return inventory_adjust_lines
