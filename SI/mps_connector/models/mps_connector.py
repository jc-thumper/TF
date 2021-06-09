# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import api, fields, _, models

from ..utils.datetime_utils import get_date_range_by_num_of_cols, find_index_of_time_range
from ...si_core.utils.string_utils import PeriodType
from ...si_core.utils.datetime_utils import convert_from_datetime_to_str_datetime

class MPSConnector(models.Model):
    _name = "mps.connector"
    _description = "MPS Connector"
    _auto = False

    ###############################
    # CONSTANT FUNCTION
    ###############################
    MIN_NUMBER_OF_COLS_MPS = 6

    ###############################
    # INIT FUNCTION
    ###############################
    def init_forecast_result_from_mps_data(self):
        """
            Synchronizing data from MPS to Forecast Base
        :return:
        :rtype:
        """
        company = self.env.user.company_id
        company_id = company.id

        # Get MPS setting info for current company
        company_number_of_cols = max(company.manufacturing_period_to_display,
                                     self.MIN_NUMBER_OF_COLS_MPS)

        # Get all the MPS demand forecast value
        demand_fore_data_dict = self.get_demand_fore_data_dict(company_id=company_id)

        # Summarize demand forecast for all period type
        if demand_fore_data_dict:
            fore_result_data = []
            for period_type, _ in PeriodType.LIST_PERIODS:
                product_demand_fore_dict = self.summarize_demand_fore_by_period(
                    period_type=period_type,
                    company_id=company_id,
                    num_of_cols=company_number_of_cols,
                    demand_fore_data_dict=demand_fore_data_dict
                )

                now = convert_from_datetime_to_str_datetime(datetime.now())

                for key, value in product_demand_fore_dict.items():
                    product_id, warehouse_id = key
                    company_id = value.get('company_id')
                    data = value.get('data')

                    for line in data:
                        start_date = convert_from_datetime_to_str_datetime(line.get('start_date'))
                        end_date = convert_from_datetime_to_str_datetime(line.get('end_date'))
                        forecast_qty = line.get('forecast_qty')

                        fore_result_data.append({
                            "product_id": product_id,
                            "company_id": company_id,
                            "warehouse_id": warehouse_id,
                            "lot_stock_id": None,
                            "algorithm": None,
                            "period_type": period_type,
                            "pub_time": now,
                            "start_date": start_date,
                            "end_date": end_date,
                            "forecast_result": forecast_qty,
                        })

            # Create and update forecast_result based on the summarized data
            forecast_level = company.forecast_level_id.name
            fore_result_env = self.env['forecast.result']

            # 1. Transform data
            fore_result_data = fore_result_env.transform_json_data_request(list_data=fore_result_data)

            # 2. Get time when records are created in the database
            created_date = fore_result_data[0].get('create_date')

            # 3. Update data to the table
            fore_result_env.create_or_update_records(vals=fore_result_data, forecast_level=forecast_level)

            # 4. Push next actions into queue jobs if it is existing
            fore_result_env.trigger_next_actions(**{
                'created_date': created_date,
                'forecast_level': forecast_level
            })

    ###############################
    # HELPER FUNCTION
    ###############################
    def summarize_demand_fore_by_period(self, period_type, company_id=None, num_of_cols=None, demand_fore_data_dict=None):
        """

        :param period_type:
        :type period_type: str
        :param company_id:
        :type company_id: int
        :param num_of_cols:
        :type num_of_cols: int
        :param demand_fore_data_dict:
        :type demand_fore_data_dict: dict
        :return: {
            (product_id, warehouse_id): {
                'company_id': company_id,
                'data': [
                    {
                        'company_id': company_id
                        'start_date': start_date,
                        'end_date': end_date,
                        'forecast_qty': forecast_qty
                    }
                ]
            }
        }
        :rtype: dict
        """
        company_id = company_id or self.env.user.company_id.id
        num_of_cols = num_of_cols or max(
            self.env['company_id'].search([('id', '=', company_id)], limit=1).manufacturing_period_to_display,
            self.MIN_NUMBER_OF_COLS_MPS)
        demand_fore_data_dict = demand_fore_data_dict or self.get_demand_fore_data_dict(company_id)

        now = datetime.now()
        date_range_list = get_date_range_by_num_of_cols(now, period_type, num_of_cols)

        # Calculate the demand forecast for all period time ranges
        product_demand_fore_dict = {}
        for key, value in demand_fore_data_dict.items():
            product_id, warehouse_id = key
            company_id = value.get('company_id')

            product_demand_fore_item = product_demand_fore_dict.setdefault(
                (product_id, warehouse_id),
                {
                    'company_id': company_id,
                    'data': [
                        {
                            'start_date': date_range[0],
                            'end_date': date_range[1],
                            'forecast_qty': 0
                        }
                        for date_range in date_range_list
                    ]
                }
            )

            product_demand_fore_data = product_demand_fore_item.get('data')
            for line in value.get('data'):
                index = find_index_of_time_range(line.get('date'), date_range_list)
                if index >= 0:
                    product_demand_fore_data[index]['forecast_qty'] += line.get('forecast_qty')

            product_demand_fore_item.update({
                'data': product_demand_fore_data
            })

        return product_demand_fore_dict

    def get_demand_fore_data_dict(self, company_id=None, date_from=None, date_to=None):
        """

        :param company_id:
        :type company_id: int
        :param date_from:
        :type date_from: datetime
        :param date_to:
        :type date_to: datetime
        :return: {
            (product_id, warehouse_id): {
                'company_id': company_id,
                'data': [
                    {
                        'date': date
                        'forecast_qty': the demand forecast value
                    },
                    ...
                ]
            }
        }
        :rtype: dict
        """
        # Get MPS product info
        mps_demand_forecast_dict = {}

        self._cr.execute("""
            SELECT product_id, company_id, warehouse_id
            FROM mrp_production_schedule mps;
        """)
        for line in self._cr.dictfetchall():
            product_id = line.get('product_id')
            company_id = line.get('company_id')
            warehouse_id = line.get('warehouse_id')

            mps_demand_forecast_dict.setdefault((product_id, warehouse_id), {
                'company_id': company_id,
                'data': []
            })

        # Get the demand forecast data from MPS
        query = """
            SELECT mps.product_id, mps.warehouse_id, forecast.forecast_qty, forecast.date
            FROM mrp_production_schedule mps
                JOIN mrp_product_forecast forecast
                    ON mps.id = forecast.production_schedule_id
        """
        if company_id:
            query += """
                AND mps.company_id = {}
            """.format(company_id)

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
            warehouse_id = line.get('warehouse_id')

            item = mps_demand_forecast_dict.get((product_id, warehouse_id))
            if item:
                item['data'].append({
                    'date': line.get('date'),
                    'forecast_qty': line.get('forecast_qty')
                })

        return mps_demand_forecast_dict
