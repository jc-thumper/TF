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
    def run(self, procurements):
        """"""
        res = super(ProcurementGroup, self).run(procurements)
        for procurement in procurements:
            orderpoint_id = procurement.values.get('orderpoint_id')
            if orderpoint_id:
                rule = self._get_rule(procurement.product_id, procurement.location_id, procurement.values)
                self.env['procurement.history'].create({
                    'orderpoint_id': orderpoint_id.id,
                    'rule_id': rule.id
                })
        return res
