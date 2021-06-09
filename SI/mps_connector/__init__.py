# -*- coding: utf-8 -*-

from . import models
from . import utils

from odoo import api, SUPERUSER_ID

def init_forecast_result_from_mps_data(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['mps.connector'].sudo().init_forecast_result_from_mps_data()