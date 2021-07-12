# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _

from odoo.addons.si_core.utils.string_utils import PeriodType

_logger = logging.getLogger(__name__)


class ProcurementHistory(models.Model):
    _name = "procurement.history"

    ###############################
    # FIELDS
    ###############################
    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', 'Orderpoint')
    rule_id = fields.Many2one('stock.rule', 'Manufacture Rule')
