# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _

from odoo.addons.si_core.utils.string_utils import PeriodType

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    ###############################
    # CONSTANTS
    ###############################
    DEFAULT_FREQUENCY_UPDATE = PeriodType.WEEKLY_TYPE

    DEFAULT_SERVICE_LEVEL_WEIGHT = 25

    DEFAULT_FLAT_COST_PER_PO = '0'
    DEFAULT_FLAT_COST_PER_MO = '0'

    DEFAULT_HOLDING_COST = 20.0

    SERVICE_FACTOR_A = 96
    SERVICE_FACTOR_B = 91
    SERVICE_FACTOR_C = 85

    ###############################
    # FIELDS
    ###############################
    min_max_update_frequency = fields.Selection(PeriodType.LIST_PERIODS, string='Min/Max Updating Frequency',
                                                default=DEFAULT_FREQUENCY_UPDATE,
                                                store=True, required=True)

    service_level_a = fields.Integer(default=SERVICE_FACTOR_A, string='Service Level Categ A',
                                     store=True, required=True)
    service_level_b = fields.Integer(default=SERVICE_FACTOR_B, string='Service Level Categ B',
                                     store=True, required=True)
    service_level_c = fields.Integer(default=SERVICE_FACTOR_C, string='Service Level Categ C',
                                     store=True, required=True)

    flat_cost_per_po = fields.Float(string='Cost of Placing Purchase Ordering', store=True, required=True,
                                    help=' Setup costs (per order, generally including shipping and handling)')
    flat_cost_per_mo = fields.Float(string='Cost of Placing Manufacturing Ordering', store=True, required=True)

    holding_cost_per_inventory_value = fields.Float(string='Holding Cost Per Year', default=DEFAULT_HOLDING_COST,
                                                    store=True, required=True,
                                                    help=' How much do you spend on holding and storing inventory, per unit, per year?\n'
                                                         'holding costs usually make up 20%-30% of a business’s total cost of inventory')

    auto_apply_rule = fields.Boolean('Automatically Apply Reordering Rules', default=False)

    auto_gen_rule = fields.Boolean('Automatically generate new reordering rules if not existed!', default=True)

    ###############################
    # MODEL FUNCTIONS
    ###############################

    @api.model
    def get_company_configuration_for_rrwf(self, company_id):
        result = {}
        if company_id:
            record = self.env['res.company'].sudo().search_read(
                [('id', '=', company_id)],
                ['min_max_update_frequency', 'service_level_a', 'service_level_b', 'service_level_c',
                 'flat_cost_per_po', 'flat_cost_per_mo', 'holding_cost_per_inventory_value',
                 'auto_apply_rule', 'auto_gen_rule'])
            if record:
                result = record[0]

        return result
