# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _

from odoo.addons.si_core.utils.string_utils import PeriodType

_logger = logging.getLogger(__name__)


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    ###############################
    # PUBLIC FUNCTIONS
    ###############################
    @api.model
    def run(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        """"""
        res = super(ProcurementGroup, self).run(product_id, product_qty, product_uom, location_id, name, origin, values)
        orderpoint_id = values.get('orderpoint_id')
        if orderpoint_id:
            rule = self._get_rule(product_id, location_id, values)
            self.env['procurement.history'].create({
                'orderpoint_id': orderpoint_id.id,
                'rule_id': rule.id
            })
        return res
