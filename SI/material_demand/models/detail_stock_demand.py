# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class DetailStockDemand(models.Model):
    _name = 'detail.stock.demand'

    prod_bom_id = fields.Many2one('product.bom.info', required=True)
    source_line_id = fields.Many2one('forecast.result.adjust.line', required=True)
    affected_line_id = fields.Many2one('forecast.result.adjust.line', required=True)
    no_days_affect = fields.Integer(string=_('Number of Days Affect'), required=True)
    affect_from = fields.Date(required=True)
    affect_to = fields.Date(required=True)

    _sql_constraints = [
        ('indirect_flow_uniq', 'unique (source_line_id, affected_line_id)',
         'You can not have more two information line have same source demand and the affected line!'),
    ]
