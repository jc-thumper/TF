# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class Warehouse(models.Model):
    _inherit = "stock.warehouse"
    _order = "sequence asc"

    sequence = fields.Integer()
