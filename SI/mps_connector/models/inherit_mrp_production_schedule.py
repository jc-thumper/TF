# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import api, fields, _, models

from ..utils.datetime_utils import get_date_range_by_num_of_cols, find_index_of_time_range
from ..utils.string_utils import get_correct_period_type
from ...si_core.utils.string_utils import PeriodType
from ...si_core.utils.datetime_utils import convert_from_datetime_to_str_datetime


class MrpProductionSchedule(models.Model):
    _inherit = "mrp.production.schedule"

    ###############################
    # CONSTANT FUNCTION
    ###############################
    MIN_NUMBER_OF_COLS_MPS = 6

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
                num_of_cols = max(company.manufacturing_period_to_display, self.MIN_NUMBER_OF_COLS_MPS)

                # Summarize demand forecast for all period type
                company_fore_result_data = []
                for period_type, _ in PeriodType.LIST_PERIODS:
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

                # 1. Transform data
                company_transformed_fore_result_data = fore_result_env.transform_json_data_request(
                    list_data=company_fore_result_data
                )

                if company_transformed_fore_result_data:
                    # 2. Get time when records are created in the database
                    created_date = company_transformed_fore_result_data[0].get('create_date')

                    # 3. Update data to the table
                    forecast_level = company.forecast_level_id.name
                    fore_result_env.create_or_update_records(
                        vals=company_transformed_fore_result_data,
                        forecast_level=forecast_level
                    )

                    # 4. Push next actions into queue jobs if it is existing
                    fore_result_env.trigger_next_actions(**{
                        'created_date': created_date,
                        'forecast_level': forecast_level
                    })

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
        num_of_cols = max(num_of_cols, self.MIN_NUMBER_OF_COLS_MPS) \
            if num_of_cols is not None \
            else max(self.env['res.company'].search([('id', '=', company_id)], limit=1).manufacturing_period_to_display,
                     self.MIN_NUMBER_OF_COLS_MPS)

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

        # Get the demand forecast data from MPS
        query = """
            SELECT mps.product_id, mps.company_id, mps.warehouse_id, 
                   forecast.forecast_qty, forecast.date
            FROM mrp_production_schedule mps
                JOIN mrp_product_forecast forecast
                    ON mps.id = forecast.production_schedule_id
        """

        if date_from and date_to:
            query += """
                    AND forecast.date >= {}
                    AND forecast.date <= {}
            """.format(date_from, date_from)

        query += """
            ORDER BY forecast.date ASC
        """
        self._cr.execute(query)

        for line in self._cr.dictfetchall():
            product_id = line.get('product_id')
            company_id = line.get('company_id')
            warehouse_id = line.get('warehouse_id')

            data = mps_demand_forecast_dict.get((product_id, company_id, warehouse_id)) or []
            data.append({
                'date': line.get('date'),
                'forecast_qty': line.get('forecast_qty')
            })

            mps_demand_forecast_dict[(product_id, company_id, warehouse_id)] = data

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
