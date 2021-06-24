# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
import pandas as pd

from odoo import api, fields, _, models

from ..utils.datetime_utils import get_date_range_by_num_of_cols, find_index_of_time_range
from ..utils.string_utils import get_correct_period_type
from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.addons.si_core.utils.datetime_utils import convert_from_datetime_to_str_datetime, \
    get_start_end_date_value, get_delta_time

_logger = logging.getLogger()


class MrpProductionSchedule(models.Model):
    _inherit = "mrp.production.schedule"

    ###############################
    # CONSTANT FUNCTION
    ###############################
    NO_POINT_FORECAST_RESULT_DATA = {
        PeriodType.DAILY_TYPE: 180,
        PeriodType.WEEKLY_TYPE: 26,
        PeriodType.MONTHLY_TYPE: 6,
        PeriodType.QUARTERLY_TYPE: 2,
        PeriodType.YEARLY_TYPE: 1
    }

    NO_POINT_SUMMARIZED_DATA = {
        PeriodType.DAILY_TYPE: 25,
        PeriodType.WEEKLY_TYPE: 6,
        PeriodType.MONTHLY_TYPE: 6,
        PeriodType.QUARTERLY_TYPE: 6,
        PeriodType.YEARLY_TYPE: 6
    }

    ###############################
    # INIT FUNCTION
    ###############################
    def init_forecast_result_from_mps_data(self, demand_fore_data_dict=None):
        """
            Synchronizing data from MPS to Forecast Base
        :param demand_fore_data_dict: {
            (product_id, company_id, warehouse_id): [
                {
                    'date': date
                    'forecast_qty': the demand forecast value
                },
                ...
            ]
        }
        :type demand_fore_data_dict: dict
        :return:
        :rtype:
        """
        # Get all the MPS demand forecast value
        demand_fore_data_dict = demand_fore_data_dict or self.get_demand_fore_data_dict()

        # Init the MPS demand forecast data for all companies
        if demand_fore_data_dict:
            fore_result_env = self.env['forecast.result']
            now = convert_from_datetime_to_str_datetime(datetime.now())

            companies = self.env['res.company'].search([])
            for company in companies:
                company_id = company.id
                company_no_cols = company.manufacturing_period_to_display

                # Summarize demand forecast for all period type
                company_fore_result_data = []
                for period_type, _ in PeriodType.LIST_PERIODS:
                    num_of_cols = max(company_no_cols,
                                      self.NO_POINT_FORECAST_RESULT_DATA.get(period_type, company_no_cols))

                    product_demand_fore_dict = self.summarize_demand_fore_by_period(
                        period_type=period_type,
                        company_id=company_id,
                        num_of_cols=num_of_cols,
                        demand_fore_data_dict=demand_fore_data_dict
                    )

                    for key, value in product_demand_fore_dict.items():
                        product_id, _, warehouse_id = key

                        for line in value:
                            start_date = convert_from_datetime_to_str_datetime(line.get('start_date'))
                            end_date = convert_from_datetime_to_str_datetime(line.get('end_date'))
                            forecast_qty = line.get('forecast_qty')

                            company_fore_result_data.append({
                                'product_id': product_id,
                                'company_id': company_id,
                                'warehouse_id': warehouse_id,
                                'lot_stock_id': None,
                                'algorithm': None,
                                'period_type': period_type,
                                'pub_time': now,
                                'start_date': start_date,
                                'end_date': end_date,
                                'forecast_result': forecast_qty,
                            })

                if company_fore_result_data:
                    self._create_or_update_model_data(company=company,
                                                      data=company_fore_result_data,
                                                      model=fore_result_env)

    def init_product_fore_config_from_mps_data(self, demand_fore_data_dict=None):
        """
            With the MPS data, create the Product Forecast Configuration for all products
            in the MPS
        :param demand_fore_data_dict: {
            (product_id, company_id, warehouse_id): [
                {
                    'date': date
                    'forecast_qty': the demand forecast value
                },
                ...
            ]
        }
        :type demand_fore_data_dict: dict
        :return:
        :rtype:
        """
        # Get all the MPS demand forecast value
        demand_fore_data_dict = demand_fore_data_dict or self.get_demand_fore_data_dict()

        # Create the product forecast configuration for all products in MPS
        if demand_fore_data_dict:
            prod_fore_config_env = self.env['product.forecast.config'].sudo()

            # Get all companies mps settings info
            mps_settings_dict = self.get_all_companies_mps_settings()

            # Get the product forecast configuration dict to prevent duplicate issue
            product_config_dict = self._get_product_fore_config_dict()
            new_demand_fore_data_dict = {
                key: value
                for key, value in demand_fore_data_dict.items()
                if key not in product_config_dict
            }

            new_prod_fore_config = []
            # Generate the configuration
            for key, _ in new_demand_fore_data_dict.items():
                product_id, company_id, warehouse_id = key
                company_period_type = mps_settings_dict.get(company_id, {})\
                    .get('period_type', 'daily')

                new_prod_fore_config.append({
                    'product_id': product_id,
                    'company_id': company_id,
                    'warehouse_id': warehouse_id,

                    'auto_update': False,
                    'period_type_custom': company_period_type,
                    'period_type': company_period_type,
                    'frequency_custom': company_period_type,
                    'frequency': company_period_type,
                    'no_periods_custom': 0
                })

            # Create the Product Forecast Configuration
            if new_prod_fore_config:
                prod_fore_config_env.create(new_prod_fore_config)

    def init_summarized_historical_data(self):
        """
            Summarize the historical demand in the case that don't have the available summarised data
            when computing the Reordering points
        :return:
        :rtype:
        """
        # Get the summarized historical data
        now = datetime.now()
        summarized_rec_result_env = self.env['summarize.rec.result']
        warehouses = self.env['stock.warehouse'].sudo().search([])

        companies = self.env['res.company'].search([])
        for company in companies:
            company_id = company.id
            warehouse_ids = warehouses.filtered(lambda x: x.company_id.id == company_id).ids
            summarize_rec_result_data = []

            # Summarize historical data for all period type
            for period_type, _ in PeriodType.LIST_PERIODS:
                no_cols = self.NO_POINT_SUMMARIZED_DATA.get(period_type, 6)

                summarized_data_dict = self._summarize_historical_data_by_period(company.sudo(), warehouse_ids,
                                                                                 period_type, no_cols)
                for product_id, summarized_data_by_warehouse in summarized_data_dict.items():
                    for warehouse_id, summarized_data in summarized_data_by_warehouse.items():
                        for line in summarized_data:
                            start_date = line.get('start_date')
                            end_date = line.get('end_date')
                            summarize_value = line.get('summarize_result', 0)

                            summarize_rec_result_data.append({
                                'product_id': product_id,
                                'company_id': company_id,
                                'warehouse_id': warehouse_id,
                                'period_type': period_type,
                                'pub_time': now,
                                'start_date': start_date,
                                'end_date': end_date,
                                'summarize_value': summarize_value,
                                'no_picks': 0,
                                'picks_with_discount': 0,
                                'demand_with_discount': 0,
                                'avg_discount_perc': 0
                            })

            if summarize_rec_result_data:
                self._create_or_update_model_data(company=company,
                                                  data=summarize_rec_result_data,
                                                  model=summarized_rec_result_env)

    ###############################
    # HELPER FUNCTION
    ###############################
    def summarize_demand_fore_by_period(self, period_type, company_id, num_of_cols=None, demand_fore_data_dict=None):
        """
            Summarize the demand forecast base on the period type.
            Ex: If the period is Weekly and the num_of_cols (get from the company mps setting) is 6
            Based on the demand_fore_data_dict, the function will calculate the total demand forecast
            from now to the next 5th date.
            So the return value will be a list containing the total demand forecast
            sum by date: [demand forecast of the current week, demand forecast of next week, ...,
            demand forecast of the next 5th week]
        :param period_type:
        :type period_type: str
        :param company_id:
        :type company_id: int
        :param num_of_cols:
        :type num_of_cols: int
        :param demand_fore_data_dict:
        :type demand_fore_data_dict: dict
        :return: {
            (product_id, company_id, warehouse_id): [
                {
                    'start_date': start_date,
                    'end_date': end_date,
                    'forecast_qty': forecast_qty
                }
            ]
        }
        :rtype: dict
        """
        # Get the demand forecast dict
        demand_fore_data_dict = demand_fore_data_dict or self.get_demand_fore_data_dict()

        now = datetime.now()
        date_range_list = get_date_range_by_num_of_cols(now, period_type, num_of_cols)

        # Calculate the demand forecast for all period time ranges
        product_demand_fore_dict = {}
        for key, value in demand_fore_data_dict.items():
            _, in_dict_company_id, _ = key

            if in_dict_company_id == company_id:
                product_demand_fore_item = product_demand_fore_dict.setdefault(
                    key, [
                        {
                            'start_date': date_range[0],
                            'end_date': date_range[1],
                            'forecast_qty': 0
                        }
                        for date_range in date_range_list
                    ]
                )

                for line in value:
                    index = find_index_of_time_range(line.get('date'), date_range_list)
                    if index >= 0:
                        product_demand_fore_item[index]['forecast_qty'] += line.get('forecast_qty')

                product_demand_fore_dict[key] = product_demand_fore_item

        return product_demand_fore_dict

    def get_demand_fore_data_dict(self, date_from=None, date_to=None):
        """
            Get the demand forecast data from MPS for all companies from date_from to date_to.
            If there are no date_from and date_to parameters, get the demand forecast data
            for all date.
        :param date_from:
        :type date_from: datetime
        :param date_to:
        :type date_to: datetime
        :return: {
            (product_id, company_id, warehouse_id): [
                {
                    'date': date
                    'forecast_qty': the demand forecast value
                },
                ...
            ]
        }
        :rtype: dict
        """
        mps_demand_forecast_dict = {}

        # Get the product' info from MPS
        self._cr.execute("""
            SELECT product_id, company_id, warehouse_id
            FROM mrp_production_schedule;
        """)
        for line in self._cr.dictfetchall():
            key = (line.get('product_id'), line.get('company_id'), line.get('warehouse_id'))
            mps_demand_forecast_dict.setdefault(key, {})

        # Get the demand forecast data from MPS
        sql_query = """
            SELECT mps.product_id, mps.company_id, mps.warehouse_id, 
                   forecast.forecast_qty, forecast.date
            FROM mrp_production_schedule mps
                JOIN mrp_product_forecast forecast
                    ON mps.id = forecast.production_schedule_id
        """

        if date_from and date_to:
            sql_query += """
                    AND forecast.date >= {}
                    AND forecast.date <= {}
            """.format(date_from, date_from)

        sql_query += """
            ORDER BY forecast.date ASC
        """
        self._cr.execute(sql_query)

        for line in self._cr.dictfetchall():
            key = (line.get('product_id'), line.get('company_id'), line.get('warehouse_id'))

            data = mps_demand_forecast_dict.get(key) or []
            data.append({
                'date': line.get('date'),
                'forecast_qty': line.get('forecast_qty')
            })

            mps_demand_forecast_dict[key] = data

        # If the product is in the MPS, but there's no demand forecast point for that products,
        # create a fake demand forecast point with forecast_qty is 0 and date is current date
        # to keep the MPS continuing to calculate the forecast demand for that product
        now = datetime.now().date()
        for key, data in mps_demand_forecast_dict.items():
            if not data:
                mps_demand_forecast_dict[key] = [{
                    'date': now,
                    'forecast_qty': 0
                }]

        return mps_demand_forecast_dict

    def get_all_companies_mps_settings(self):
        """
            Return a dict contains all companies' mps settings included period_type and
            num_of_cols
        :return: {
            company_id: {
                'period_type': company.manufacturing_period,
                'num_of_cols': company.manufacturing_period_to_display,
            }
        }
        :rtype: dict
        """
        mps_settings_dict = {}
        companies = self.env['res.company'].search([])

        for company in companies:
            period_type = get_correct_period_type(company.manufacturing_period) or PeriodType.WEEKLY_TYPE
            num_of_cols = company.manufacturing_period_to_display

            mps_settings_dict.setdefault(company.id, {
                'period_type': period_type,
                'num_of_cols': num_of_cols
            })

        return mps_settings_dict

    ###############################
    # PRIVATE FUNCTION
    ###############################
    def _get_product_fore_config_dict(self):
        """
            Get all the products' forecast configuration included id
            and period_type
        :return: {
            (product_id, company_id, warehouse_id): {
                'id': product_fore_config.id
                'period_type': product_fore_config.period_type
            }
        }
        :rtype: dict
        """
        product_config_dict = {}
        product_configs = self.env['product.forecast.config'].search([])
        for config in product_configs:
            config_id = config.id
            product_id = config.product_id.id
            company_id = config.company_id.id
            warehouse_id = config.warehouse_id.id

            if config.auto_update and config.forecast_group_id:
                period_type = config.forecast_group_id.period_type
            else:
                period_type = config.period_type_custom

            product_config_dict.setdefault(
                (product_id, company_id, warehouse_id),
                {
                    'id': config_id,
                    'period_type': period_type
                }
            )

        return product_config_dict

    def _get_list_products_have_sold(self, company_id, timezone, date_from):
        """

        :param range_date:
        :type range_date:
        :type company_id: int
        :type timezone: str
        :return:
        Ex: {
                product_id: number_of_orders
            }
        :rtype: dict
        """
        start_date = str(date_from)
        query = """
                SELECT product_id, COUNT(*) num_of_orders
                FROM sale_order_line
                       JOIN sale_order
                         ON sale_order_line.order_id = sale_order.id
                WHERE date_order :: TIMESTAMPTZ AT TIME ZONE %(timezone)s >= %(start_date)s
                    AND product_id IS NOT NULL
                    AND sale_order.company_id = %(company_id)s 
                GROUP BY product_id
        """
        self.env.cr.execute(query, {'start_date': start_date, 'company_id': company_id, 'timezone': timezone})
        return dict([(i['product_id'], i['num_of_orders']) for i in self.env.cr.dictfetchall()])

    def _get_historical_data(self, company, date_from):
        """
            Get product daily demand from date_from to current date. (by company)
        :param company:
        :type company: ResCompany
        :param date_from:
        :type date_from: datetime
        :return: {
            product_id: [
                {
                    'date_order': the date_order of the sale orders,
                    'warehouse_id': the warehouse_id on the sale orders
                    'summarize_result': product demand of the sale orders in the date_order date
                }
            ]
        }
        :type: dict
        """
        product_daily_demand_dict = {}
        company_id = company.id
        try:
            timezone = company.timezone
            current_date = datetime.now()

            start_date_range = convert_from_datetime_to_str_datetime(date_from)
            end_date_range = convert_from_datetime_to_str_datetime(current_date)

            so_state_affect_percentage_dict = company.get_so_state_affect_percentage_dict(company)

            # Get records from client db
            sql_query = """
                SELECT product_uom_qty / uu.factor AS units,
                    o.warehouse_id,
                    o.state,
                    o.date_order :: TIMESTAMPTZ AT TIME ZONE %(timezone)s AS converted_date,
                    product_id
                FROM sale_order o
                    JOIN sale_order_line sol ON o.id = sol.order_id
                        AND o.company_id = %(company_id)s
                        AND o.date_order :: TIMESTAMPTZ AT TIME ZONE %(timezone)s >= %(start_date_range)s
                        AND o.date_order :: TIMESTAMPTZ AT TIME ZONE %(timezone)s <= %(end_date_range)s
                JOIN product_product ON product_product.id = sol.product_id
                JOIN uom_uom uu ON uu.id = sol.product_uom;
            """
            sql_params = {
                'company_id': company_id,
                'timezone': timezone,
                'start_date_range': start_date_range,
                'end_date_range': end_date_range
            }
            self.env.cr.execute(sql_query, sql_params)

            # Fetch the result
            product_daily_demand = self.env.cr.dictfetchall()
            _logger.info("Read %d rows from sales data to summarize" % (len(product_daily_demand),))

            unique_product_ids = list(self._get_list_products_have_sold(company_id, timezone, date_from).keys())

            if len(product_daily_demand) > 0:
                # Convert to DataFrame
                df = pd.DataFrame.from_records(product_daily_demand)

                df['date_order'] = df['converted_date'].dt.to_period('D')\
                    .apply(lambda r: r.start_time)

                df['pre_agg'] = df.apply(
                    lambda r: r['units'] * so_state_affect_percentage_dict
                        .get(r['state'], {})
                        .get('affect_percentage', 0) / 100, axis=1)

                # Summarize data by period type
                group_by_cols = ['product_id', 'date_order']
                grouped_df = df.groupby(group_by_cols).agg({
                    'units': 'sum'
                }).reset_index()

                # Rename columns
                grouped_df = grouped_df.rename(columns={
                    'units': 'summarize_result'
                })

            # Create the product daily demand data dict
            for product_id in unique_product_ids:
                if grouped_df is not None and not grouped_df.empty:
                    product_df = grouped_df.query(
                        'product_id == %d' % (product_id, ))

                    # Remove product_id column from datafram
                    del product_df['product_id']

                    product_daily_demand_dict[product_id] = product_df.to_dict('records')

        except:
            _logger.error('Having some problems when summarizing sale order data '
                          'for company %s'
                          % (company_id,), exc_info=True)

        return product_daily_demand_dict

    def _summarize_historical_data_by_period(self, company, warehouse_ids, period_type, no_cols):
        """
            Summarize the historical data from _get_summarize_historical_data by period type
        :param company
        :type company: ResCompany
        :param warehouse_ids
        :type warehouse_ids: list[int]
        :param period_type:
        :type period_type: str`
        :param no_cols:
        :type no_cols: int
        :return: {
            product_id: {
                warehouse_id: [
                    {
                        'start_date': the start date of time range,
                        'end_date': the end date of time range,
                        'summarize_value': the summarized value in the period from start_date to end_date
                    }
                ]
            }
        }
        :rtype: dict
        """
        now = datetime.now()
        date_range_list = get_date_range_by_num_of_cols(now, period_type, no_cols)

        # Get the historical data from db
        date_from = get_start_end_date_value(now - get_delta_time(period_type, no_cols), period_type)[0]
        historical_data_dict = self._get_historical_data(company, date_from)

        # Summarize the historical data by period
        summarized_data_dict = {}
        for product_id, historical_data in historical_data_dict.items():
            summarized_product_data_dict = {}

            for warehouse_id in warehouse_ids:
                summarized_data_item = summarized_product_data_dict.setdefault(warehouse_id, [
                    {
                        'start_date': date_range[0],
                        'end_date': date_range[1],
                        'summarize_value': 0
                    }
                    for date_range in date_range_list
                ])

                for line in historical_data:
                    if line.get('warehouse_id') == warehouse_id:
                        index = find_index_of_time_range(line.get('date_order'), date_range_list)
                        if index >= 0:
                            summarized_data_item[index]['summarize_value'] += line.get('summarize_result')

                summarized_product_data_dict[warehouse_id] = summarized_data_item

            summarized_data_dict.setdefault(product_id, summarized_product_data_dict)

        return summarized_data_dict

    @staticmethod
    def _create_or_update_model_data(company, data, model):
        """
            Middle-ware between target model and the mps connector, to handle push data
            from mps connector to target model, works the same way as handle_push_data_request
            on forecast_connector
        :param data:
        :type data:
        :param model:
        :type model:
        :return:
        :rtype:
        """
        # 1. Transform data
        transformed_data = model.transform_json_data_request(
            list_data=data
        )

        if transformed_data:
            # 2. Get time when records are created in the database
            created_date = transformed_data[0].get('create_date')

            # 3. Update data to the table
            forecast_level = company.forecast_level_id.name
            model.sudo().create_or_update_records(
                vals=transformed_data,
                forecast_level=forecast_level
            )

            # 4. Push next actions into queue jobs if it is existing
            model.sudo().trigger_next_actions(**{
                'created_date': created_date,
                'forecast_level': forecast_level
            })
