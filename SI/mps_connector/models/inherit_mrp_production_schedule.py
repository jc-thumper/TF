# -*- coding: utf-8 -*-

import logging
from datetime import datetime
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
    # EXTEND FUNCTION
    ###############################
    @api.model
    def create(self, values):
        """
            Extend the create function of MPS to calculate the forecast result value
            whenever the user add a new product to MPS
        :param dict values:
        :return:
        :rtype:
        """
        res = super(MrpProductionSchedule, self).create(values)

        # After creating a MPS, the demand forecast value of the MPS is empty,
        # we have to create a fake demand forecast (value = 0) to let the calculation continuing
        if res:
            now = datetime.now().date()
            demand_fore_data_dict = {
                (res.product_id.id, res.company_id.id, res.warehouse_id.id): [{
                    'date': now,
                    'forecast_qty': 0
                }]
            }

            # 1. Generate the product forecast configuration for concerning product
            self.generate_product_forecast_configuration(demand_fore_data_dict=demand_fore_data_dict)

            # 2. Generate the forecast result for concerning product
            self.generate_forecast_result(demand_fore_data_dict=demand_fore_data_dict)

            # 3. Summarize the historical data for concerning product
            self.generate_summarized_historical_demand(demand_fore_data_dict=demand_fore_data_dict)

        return res

    ###############################
    # HELPER FUNCTION
    ###############################
    def summarize_demand_fore_by_period(self, period_type, company_id, no_cols=None,
                                        demand_fore_data_dict=None, product_ids=None):
        """
            Summarize the demand forecast base on the period type.

            Ex: If the period is Weekly and the no_cols (get from the company mps setting) is 6
            Based on the demand_fore_data_dict, the function will calculate the total demand forecast
            from now to the next 5th date.

            So the return value will be a list containing the total demand forecast
            sum by date: [demand forecast of the current week, demand forecast of next week, ...,
            demand forecast of the next 5th week]
        :param str period_type:
        :param int company_id:
        :param int no_cols:
        :param dict demand_fore_data_dict:
        :param list[int] product_ids: If this value is set, summarize demand forecast for product in product_ids
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

        # Generate the date_range_list from current date to the next no_cols th period of period_type
        now = datetime.now()
        date_range_list = get_date_range_by_num_of_cols(now, period_type, no_cols)

        # Calculate the demand forecast for the whole date_range_list
        product_demand_fore_dict = {}
        for key, value in demand_fore_data_dict.items():
            in_dict_product_id, in_dict_company_id, _ = key

            # If the product_ids value is set and the current product not in product_ids,
            # do nothing
            if (product_ids is not None) and (in_dict_product_id not in product_ids):
                continue

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

    def get_demand_fore_data_dict(self, date_from=None, date_to=None, company_id=None):
        """
            Get the demand forecast data from MPS for all companies from date_from to date_to.
            If there are no date_from and date_to parameters, get the demand forecast data
            for all date.
            If the company_id parameter exist, get the data for only company_id
        :param datetime date_from:
        :param datetime date_to:
        :param int company_id:
        :return: {
            (product_id, company_id, warehouse_id): [
                {
                    'date': date,
                    'forecast_qty': the demand forecast value
                },
                ...
            ]
        }
        :rtype: dict
        """
        # Get the product' info from MPS
        mps_demand_forecast_dict = {}

        sql_query = """
            SELECT product_id, company_id, warehouse_id
            FROM mrp_production_schedule
        """
        if company_id:
            sql_query += """
                WHERE company_id = {}
            """.format(company_id)

        self._cr.execute(sql_query)
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
            Return a dict contains all companies' mps settings included period_type and no_cols
        :return: {
            company_id: {
                'period_type': company.manufacturing_period,
                'no_cols': company.manufacturing_period_to_display,
            }
        }
        :rtype: dict
        """
        mps_settings_dict = {}
        companies = self.env['res.company'].search([])

        for company in companies:
            period_type = get_correct_period_type(company.manufacturing_period) or PeriodType.WEEKLY_TYPE
            no_cols = company.manufacturing_period_to_display

            mps_settings_dict.setdefault(company.id, {
                'period_type': period_type,
                'no_cols': no_cols
            })

        return mps_settings_dict

    def create_fore_res_for_all_periods_based_on_product_fore(self, product_forecast_obj):
        """
            Create the forecast result for all period type of a product in MPS
            whenever the user update the value of demand forecast
        :param MrpProductForecast product_forecast_obj:
        :return:
        :rtype:
        """
        now = datetime.now()
        fore_result_env = self.env['forecast.result']

        # Get the MPS data from product_fore_obj
        mps = product_forecast_obj.production_schedule_id
        mps_product_fores = mps.forecast_ids
        company = mps.company_id
        product_id = mps.product_id.id
        company_id = company.id
        warehouse_id = mps.warehouse_id.id
        forecast_datetime = datetime.combine(product_forecast_obj.date, datetime.min.time())

        # Generate an empty forecast result for all period type
        fore_result_data = []
        for period_type, _ in PeriodType.LIST_PERIODS:
            start_date, end_date = get_start_end_date_value(forecast_datetime, period_type)
            fore_result_data.append({
                'product_id': product_id,
                'company_id': company_id,
                'warehouse_id': warehouse_id,
                'lot_stock_id': None,
                'algorithm': None,
                'period_type': period_type,
                'pub_time': now,
                'start_date': convert_from_datetime_to_str_datetime(start_date),
                'end_date': convert_from_datetime_to_str_datetime(end_date),
                'forecast_result': 0,
            })

        # Update forecast result to the fore_result_data
        for fore_result_item in fore_result_data:
            start_date = fore_result_item.get('start_date')
            end_date = fore_result_item.get('end_date')

            product_fores_in_period = mps_product_fores.filtered(
                lambda pro_fore: start_date <= convert_from_datetime_to_str_datetime(pro_fore.date) <= end_date
            )

            fore_result_item['forecast_result'] = sum(product_fores_in_period.mapped('forecast_qty'))

        # Create forecast_result records and trigger for the next action
        self._create_or_update_model_data(company=company,
                                          data=fore_result_data,
                                          model=fore_result_env)

    def generate_summarized_historical_demand(self, demand_fore_data_dict=None):
        """
            Summarize the historical demand in the case that don't have the available summarised data
            when computing the Reordering points
            Only compute for product in MPS
        :param dict demand_fore_data_dict:
        :return:
        :rtype:
        """
        # Get the demand forecast dict from MPS
        demand_fore_data_dict = demand_fore_data_dict or self.get_demand_fore_data_dict()
        product_ids_by_company = {}
        for key, _ in demand_fore_data_dict.items():
            product_id, company_id, _ = key

            product_ids = product_ids_by_company.setdefault(company_id, [])
            product_ids.append(product_id)

        # Get the product forecast configuration
        prod_fore_config = self._get_product_fore_config_dict(group_by_period=True)

        # Get the summarized historical data
        now = datetime.now()
        summarized_rec_result_env = self.env['summarize.rec.result']

        # Define date_from variable to get data for summarizing
        date_from = now
        for period_type, no_cols in self.NO_POINT_SUMMARIZED_DATA.items():
            date_from = min(date_from,
                            get_start_end_date_value(now - get_delta_time(period_type, no_cols), period_type)[0])

        # Generate the summarized data by company
        companies = self.env['res.company'].search([])
        for company in companies:
            company_id = company.id

            # Re-define the summarize_rec_result_data list for every company
            summarize_rec_result_data = []

            # Get the product_ids for concerning company
            product_ids = product_ids_by_company.get(company_id)

            # Get the historical data by company
            historical_data_dict = self._get_historical_data(company=company,
                                                             date_from=date_from,
                                                             product_ids=product_ids)

            if historical_data_dict:
                for period_type, _ in PeriodType.LIST_PERIODS:
                    no_cols = self.NO_POINT_SUMMARIZED_DATA.get(period_type, 6)

                    # Get list of products have product_forecast_configuration' period_type
                    # equal the current concerning period_type
                    product_ids_by_period = [
                        item.get('product_id')
                        for item in prod_fore_config.get(period_type, [])
                    ]

                    # Summarize historical data by period_type based on the historical_data_dict
                    summarized_data_dict = self._summarize_historical_data_by_period(
                        company=company.sudo(),
                        period_type=period_type,
                        no_cols=no_cols,
                        historical_data_dict=historical_data_dict,
                        product_ids=product_ids_by_period
                    )

                    # Generate summarize_rec_result data from summarized_data_dict
                    for key, summarized_data in summarized_data_dict.items():
                        product_id, warehouse_id = key
                        for line in summarized_data:
                            start_date = line.get('start_date')
                            end_date = line.get('end_date')
                            summarize_value = line.get('summarize_value', 0)

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

                # Create the summarize_rec_result records and trigger for the next action
                if summarize_rec_result_data:
                    self._create_or_update_model_data(company=company,
                                                      data=summarize_rec_result_data,
                                                      model=summarized_rec_result_env)

    def generate_product_forecast_configuration(self, demand_fore_data_dict=None):
        """
            Create the Product Forecast Configuration for all products in the MPS
            based on the company MPS settings
        :param dict demand_fore_data_dict: {
            (product_id, company_id, warehouse_id): [
                {
                    'date': date
                    'forecast_qty': the demand forecast value
                },
                ...
            ]
        }
        :return:
        :rtype:
        """
        # Get all the MPS demand forecast value
        demand_fore_data_dict = demand_fore_data_dict or self.get_demand_fore_data_dict()

        has_data = False

        # Create the product forecast configuration for all products in MPS
        if demand_fore_data_dict:
            prod_fore_config_env = self.env['product.forecast.config'].sudo()

            # Get all companies mps settings info
            mps_settings_dict = self.get_all_companies_mps_settings()

            # Get the product forecast configuration dict to prevent duplicate issue
            product_config_dict = self._get_product_fore_config_dict()
            new_demand_fore_data_dict = {}
            existing_demand_fore_ids = []
            for key, value in demand_fore_data_dict.items():
                if key in product_config_dict:
                    # If existing the product forecast configuration, add the id to
                    # existing_demand_fore_ids
                    prod_fore_config_id = product_config_dict.get(key, {}).get('id')
                    if prod_fore_config_id:
                        existing_demand_fore_ids.append(prod_fore_config_id)
                else:
                    # If there's no product forecast configuration for that key,
                    # add the key to new_demand_fore_data_dict to create a new one
                    new_demand_fore_data_dict.setdefault(key, value)

            # Update the period type for all existing product forecast configuration
            if existing_demand_fore_ids:
                has_data = True
                fore_configs = prod_fore_config_env.search([('id', 'in', existing_demand_fore_ids)])
                fore_configs.mapped('company_id')
                for config in fore_configs:
                    company_id = config.company_id.id
                    company_period_type = mps_settings_dict.get(company_id, {}) \
                        .get('period_type', 'daily')
                    config.write({
                        'auto_update': False,
                        'period_type_custom': company_period_type,
                        'period_type': company_period_type,
                        'frequency_custom': company_period_type,
                        'frequency': company_period_type,
                        'no_periods_custom': 0
                    })

            # Generate the configuration for all products which have not any forecast configuration
            new_prod_fore_config = []
            for key, _ in new_demand_fore_data_dict.items():
                product_id, company_id, warehouse_id = key
                company_period_type = mps_settings_dict.get(company_id, {}) \
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
                has_data = True
                prod_fore_config_env.create(new_prod_fore_config)

        if has_data:
            self.flush()

    def generate_forecast_result(self, demand_fore_data_dict):
        """
            Generate the forecast result data for all products in MPS.
        :param dict demand_fore_data_dict: {
            (product_id, company_id, warehouse_id): [
                {
                    'date': date
                    'forecast_qty': the demand forecast value
                },
                ...
            ]
        }
        :return:
        :rtype:
        """
        # Get all the MPS demand forecast value
        demand_fore_data_dict = demand_fore_data_dict or self.get_demand_fore_data_dict()

        # Get the product forecast configuration
        prod_fore_config = self._get_product_fore_config_dict(group_by_period=True)

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
                    no_cols = max(company_no_cols,
                                  self.NO_POINT_FORECAST_RESULT_DATA.get(period_type, company_no_cols))

                    # Get the products have period type equal to the concerning period type
                    product_ids_by_period = [
                        item.get('product_id')
                        for item in prod_fore_config.get(period_type, [])
                    ]

                    # Summarize the demand forecast data by period_type
                    product_demand_fore_dict = self.summarize_demand_fore_by_period(
                        period_type=period_type,
                        company_id=company_id,
                        no_cols=no_cols,
                        demand_fore_data_dict=demand_fore_data_dict,
                        product_ids=product_ids_by_period
                    )

                    # Generate the forecast_result data from the summarized demand forecast values
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

                # Create the forecast_result records and trigger for the next action
                if company_fore_result_data:
                    self._create_or_update_model_data(company=company,
                                                      data=company_fore_result_data,
                                                      model=fore_result_env)

    ###############################
    # PRIVATE FUNCTION
    ###############################
    def _get_product_fore_config_dict(self, group_by_period=None):
        """
            Get all the products' forecast configuration included id and period_type
        :return:
            {
                (product_id, company_id, warehouse_id): {
                    'id': product_fore_config.id
                    'period_type': product_fore_config.period_type
                }
            } if group_by_period is not set
        or
            {
                period_type: [
                    {
                        'product_id': product_id,
                        'company_id': company_id,
                        'warehouse_id': warehouse_id,
                        'product_fore_config_id': product_fore_config.id
                    }
                ]
            }
        :rtype: dict
        """
        product_config_dict = {}

        sql_query = """
            SELECT config.id,
                   config.product_id,
                   config.warehouse_id,
                   config.company_id,
                   (CASE WHEN config.auto_update THEN g.period_type ELSE config.period_type_custom END) period_type
            FROM product_forecast_config config
            LEFT JOIN product_classification_info info
                ON config.product_clsf_info_id = info.id
            LEFT JOIN forecast_group g
                ON info.forecast_group_id = g.id
        """
        self._cr.execute(sql_query)

        for line in self._cr.dictfetchall():
            config_id = line.get('id')
            product_id = line.get('product_id')
            company_id = line.get('company_id')
            warehouse_id = line.get('warehouse_id')
            period_type = line.get('period_type')

            if group_by_period:
                product_list = product_config_dict.setdefault(period_type, [])
                product_list.append({
                    'product_id': product_id,
                    'company_id': company_id,
                    'warehouse_id': warehouse_id,
                    'product_fore_config_id': config_id
                })
            else:
                product_config_dict.setdefault(
                    (product_id, company_id, warehouse_id),
                    {
                        'id': config_id,
                        'period_type': period_type
                    }
                )

        return product_config_dict

    def _get_list_products_have_sold(self, company_id, timezone, date_from, product_ids=None):
        """
            Get list of product have been sold from date_from to current date
        :param int company_id:
        :param str timezone:
        :param datetime timezone:
        :param list[int] product_ids:
        :return:
        Ex: {
            (product_id, warehouse_id): number of orders
        }
        :rtype: dict
        """
        start_date = str(date_from)
        sql_params = {}
        sql_query = """
                SELECT product_id, warehouse_id, COUNT(*) num_of_orders
                FROM sale_order_line
                       JOIN sale_order
                         ON sale_order_line.order_id = sale_order.id
        """

        if product_ids:
            sql_query += """
                            AND product_id IN %(product_ids)s
            """
            sql_params.update({
                'product_ids': tuple(product_ids)
            })

        sql_query += """
                WHERE date_order :: TIMESTAMPTZ AT TIME ZONE %(timezone)s >= %(start_date)s
                    AND product_id IS NOT NULL
                    AND sale_order.company_id = %(company_id)s 
                GROUP BY product_id, warehouse_id
        """
        sql_params.update({
            'start_date': start_date,
            'company_id': company_id,
            'timezone': timezone
        })
        self.env.cr.execute(sql_query, sql_params)

        return dict([
            ((i['product_id'], i['warehouse_id']), i['num_of_orders'])
            for i in self.env.cr.dictfetchall()
        ])

    def _get_historical_data(self, company, date_from, product_ids=None):
        """
            Get product daily demand from date_from to current date. (by company)
            If the product_ids parameter is set, get historical data for only those products
        :param ResCompany company:
        :param datetime date_from:
        :param list[int] product_ids:
        :return: {
            (product_id, warehouse_id): [
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
            sql_params = {}
            sql_query = """
                SELECT product_uom_qty / uu.factor AS units,
                    o.warehouse_id,
                    o.state,
                    o.date_order :: TIMESTAMPTZ AT TIME ZONE %(timezone)s AS converted_date,
                    product_id
                FROM sale_order o
                    JOIN sale_order_line sol ON o.id = sol.order_id
            """

            if product_ids:
                sql_query += """
                        AND sol.product_id IN %(product_ids)s
                """
                sql_params.update({
                    'product_ids': tuple(product_ids)
                })

            sql_query += """
                        AND o.company_id = %(company_id)s
                        AND o.date_order :: TIMESTAMPTZ AT TIME ZONE %(timezone)s >= %(start_date_range)s
                        AND o.date_order :: TIMESTAMPTZ AT TIME ZONE %(timezone)s <= %(end_date_range)s
                JOIN product_product ON product_product.id = sol.product_id
                JOIN uom_uom uu ON uu.id = sol.product_uom;
            """
            sql_params.update({
                'company_id': company_id,
                'timezone': timezone,
                'start_date_range': start_date_range,
                'end_date_range': end_date_range
            })
            self.env.cr.execute(sql_query, sql_params)

            # Fetch the result
            product_daily_demand = self.env.cr.dictfetchall()
            _logger.info("Read %d rows from sales data to summarize" % (len(product_daily_demand),))

            unique_product_ids = list(self._get_list_products_have_sold(company_id=company_id,
                                                                        timezone=timezone,
                                                                        date_from=date_from,
                                                                        product_ids=product_ids).keys())

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
                group_by_cols = ['product_id', 'warehouse_id', 'date_order']
                grouped_df = df.groupby(group_by_cols).agg({
                    'units': 'sum'
                }).reset_index()

                # Rename columns
                grouped_df = grouped_df.rename(columns={
                    'units': 'summarize_result'
                })

            # Create the product daily demand data dict
            for product_id, warehouse_id in unique_product_ids:
                if grouped_df is not None and not grouped_df.empty:
                    product_df = grouped_df.query(
                        'product_id == %d & warehouse_id == %d' % (product_id, warehouse_id))

                    # Remove product_id column from datafram
                    del product_df['product_id']

                    product_daily_demand_dict[(product_id, warehouse_id)] = product_df.to_dict('records')

        except:
            _logger.error('Having some problems when summarizing sale order data '
                          'for company %s'
                          % (company_id,), exc_info=True)

        return product_daily_demand_dict

    def _summarize_historical_data_by_period(self, company, period_type, no_cols,
                                             historical_data_dict=None, product_ids=None):
        """
            Summarize the historical data from _get_summarize_historical_data by period type
        :param ResCompany company:
        :param str period_type:
        :param int no_cols:
        :param dict historical_data_dict:
            (product_id, warehouse_id): [
                {
                    'date_order': the date_order of the sale orders,
                    'warehouse_id': the warehouse_id on the sale orders
                    'summarize_result': product demand of the sale orders in the date_order date
                }
            ]
        :param list[int] product_ids: If this value is set, only summarize for product in product_ids
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
        date_range_list = get_date_range_by_num_of_cols(now, period_type, -no_cols)

        # Get the historical data from db if not exist
        if historical_data_dict is None:
            date_from = get_start_end_date_value(now - get_delta_time(period_type, no_cols), period_type)[0]
            historical_data_dict = self._get_historical_data(company, date_from)

        # Summarize the historical data by period
        summarized_data_dict = {}
        for key, historical_data in historical_data_dict.items():
            product_id, warehouse_id = key

            # If the product_id not in product_ids, do nothing
            if (product_ids is not None) and (product_id not in product_ids):
                continue

            # Initialize the summarized data for each (product, warehouse) by date range from period
            summarized_data_item = summarized_data_dict.setdefault((product_id, warehouse_id), [
                {
                    'start_date': date_range[0],
                    'end_date': date_range[1],
                    'summarize_value': 0
                }
                for date_range in date_range_list
            ])

            # Summarize the historical data to the dict
            for line in historical_data:
                index = find_index_of_time_range(line.get('date_order').date(), date_range_list)
                if index >= 0:
                    summarized_data_item[index]['summarize_value'] += line.get('summarize_result')

        return summarized_data_dict

    @staticmethod
    def _create_or_update_model_data(company, data, model):
        """
            Middle-ware between target model and the MPS Connector module, to handle push data
            from the MPS Connector to target model, works the same way as handle_push_data_request
            on forecast_connector
        :param ResCompany company:
        :param data:
        :type data:
        :param model:
        :type model:
        :return:
        :rtype:
        """
        model = model.sudo()

        # 1. Transform data
        transformed_data = model.transform_json_data_request(
            list_data=data
        )

        if transformed_data:
            # 2. Get time when records are created in the database
            created_date = transformed_data[0].get('create_date')

            # 3. Update data to the table
            forecast_level = company.forecast_level_id.name
            model.create_or_update_records(
                vals=transformed_data,
                forecast_level=forecast_level
            )

            # 4. Push next actions into queue jobs if it is existing
            model.trigger_next_actions(**{
                'created_date': created_date,
                'company_id': company.id,
                'forecast_level': forecast_level
            })

    ###############################
    # CRON FUNCTIONS
    ###############################
    def cron_summarized_historical_data(self):
        """
            Summarize the historical demand in the case that don't have the available summarised data
            when computing the Reordering points
        :return:
        :rtype:
        """
        self.generate_summarized_historical_demand()

    ###############################
    # INIT FUNCTION
    ###############################
    def init_forecast_result_from_mps_data(self, demand_fore_data_dict=None):
        """
            Initialize the forecast result from the MPS' data
        :param dict demand_fore_data_dict:
        :return:
        :rtype:
        """
        self.generate_forecast_result(demand_fore_data_dict)

    def init_product_fore_config_from_mps_data(self, demand_fore_data_dict=None):
        """
            Initialize the product forecast configuration for all products in MPS
        :param dict demand_fore_data_dict:
        :return:
        :rtype:
        """
        self.generate_product_forecast_configuration(demand_fore_data_dict)

    def init_summarized_historical_data(self, demand_fore_data_dict=None):
        """
            Summarize the historical demand in the case that don't have the available summarised data
            when computing the Reordering points
        :return:
        :rtype:
        """
        self.generate_summarized_historical_demand(demand_fore_data_dict)


class MrpProductForecast(models.Model):
    _inherit = "mrp.product.forecast"

    ###############################
    # FUNCTION
    ###############################
    @api.model
    def create(self, values):
        """
            Extend the MrpProductForecast's create function to handle the create event
            to re-calculate the forecast result
        :param dict values:
        :return:
        :rtype:
        """
        res = super(MrpProductForecast, self).create(values)
        res.update_forecast_result()
        return res

    def write(self, values):
        """
            Extend the MrpProductForecast's write function to handle the update/write event
            to re-calculate the forecast result
        :param dict values:
        :return:
        :rtype:
        """
        res = super(MrpProductForecast, self).write(values)
        self.update_forecast_result()
        return res

    def update_forecast_result(self):
        self.env['mrp.production.schedule'].create_fore_res_for_all_periods_based_on_product_fore(self)
