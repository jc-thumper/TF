# -*- coding: utf-8 -*-

from . import models
from . import utils

from odoo import api, SUPERUSER_ID


def setup_mps_connector(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['mrp.production.schedule'].sudo().init_forecast_result_from_mps_data()