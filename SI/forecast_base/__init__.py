# -*- coding: utf-8 -*-

from . import models
from . import wizard

from odoo.api import Environment, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = Environment(cr, SUPERUSER_ID, {})
    env['forecast.result.adjust.line'].create_index()
