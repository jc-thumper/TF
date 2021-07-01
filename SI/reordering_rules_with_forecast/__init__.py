# -*- coding: utf-8 -*-

from . import controllers
from . import models
from . import wizard
from odoo import api, SUPERUSER_ID


def init_reordering_rules_with_forecast(cr, registry):
    """Post install app reordering rules with forecast:
        Step 1: Create the index for the table reordering rules with forecast tracker
        Step 2: Update the existing rules on reordering rules in the Odoo out of the box to rrwf
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['reordering.rules.with.forecast.tracker'].create_rrwf_tracker_indices()
    env['reordering.rules.with.forecast'].create_rrwf_indices()
    env['reordering.rules.with.forecast'].init_data_reordering_rules_with_forecast()
