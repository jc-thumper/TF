# -*- coding: utf-8 -*-

from . import models
from . import utils

from odoo import api, SUPERUSER_ID


def setup_mps_connector(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    mps_env = env['mrp.production.schedule'].sudo()

    # Initial data from MPS data
    demand_fore_data_dict = mps_env.get_demand_fore_data_dict()

    # 1. Initialize the Product Forecast Configuration
    mps_env.init_product_fore_config_from_mps_data(demand_fore_data_dict=demand_fore_data_dict)

    # 2. Initialize the Forecast Result data
    mps_env.init_forecast_result_from_mps_data(demand_fore_data_dict=demand_fore_data_dict)

    # 3. Summarize the historical demand in the case that don't have the available summarised data
    # when computing the Reordering points
    mps_env.init_summarized_historical_data(demand_fore_data_dict=demand_fore_data_dict)

