# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """
    This model add some fields in Settings menu in Inventory app
    """
    _inherit = 'res.config.settings'

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
    min_max_update_frequency = fields.Selection(related='company_id.min_max_update_frequency',
                                                readonly=False, string='Min max update frequency')

    service_level_a = fields.Integer(related='company_id.service_level_a', default=SERVICE_FACTOR_A, readonly=False,
                                     string='Service Level Categ A', store=True, required=True)
    service_level_b = fields.Integer(related='company_id.service_level_b', default=SERVICE_FACTOR_B, readonly=False,
                                     string='Service Level Categ B', store=True, required=True)
    service_level_c = fields.Integer(related='company_id.service_level_c', default=SERVICE_FACTOR_C, readonly=False,
                                     string='Service Level Categ C', store=True, required=True)

    flat_cost_per_po = fields.Float(related='company_id.flat_cost_per_po',
                                    string='Cost of Placing Purchase Ordering', store=True,
                                    required=True, readonly=False)
    flat_cost_per_mo = fields.Float(related='company_id.flat_cost_per_mo',
                                    string='Cost of Placing Manufacturing Ordering', store=True,
                                    required=True, readonly=False)

    holding_cost_per_inventory_value = fields.Float(related='company_id.holding_cost_per_inventory_value',
                                                    readonly=False, string='Holding Cost', default=DEFAULT_HOLDING_COST,
                                                    store=True, required=True)

    module_forecast_preparation = fields.Boolean("Purchase Planning Extender",
                                                 help='triggers the immediate installation of the module named '
                                                      '`forecast_preparation` if the field has value ``True``')
    module_forecast_preparation_with_mrp = fields.Boolean("Manufacturing Planning Extender",
                                                          help='triggers the immediate installation of the module '
                                                               'named `forecast_preparation_with_mrp` '
                                                               'if the field has value ``True``')

    auto_apply_rule = fields.Boolean(related='company_id.auto_apply_rule', readonly=False,
                                     string='Automatically Apply Reordering Rules',
                                     help='The existing reordering rules will be automatically '
                                          'applied to the recommended')
    auto_gen_rule = fields.Boolean(related='company_id.auto_gen_rule', readonly=False,
                                   string='Automatically generate new reordering rules if not existed!',
                                   help='Odoo Reorder points will be automatically generated if it does not existed!')

    #################################
    # ONCHANGE FUNCTIONS
    #################################
    @api.onchange('service_level_a')
    def _onchange_service_level_a(self):
        if self.service_level_a < 0 or self.service_level_a > 100:
            raise ValidationError(_("Service level for Item A must be in range 96 - 98 %"))

    @api.onchange('service_level_b')
    def _onchange_service_level_b(self):
        if self.service_level_b < 0 or self.service_level_b > 100:
            raise ValidationError(_("Service level for Item B must be in range 91 - 95 %"))

    @api.onchange('service_level_c')
    def _onchange_service_level_c(self):
        if self.service_level_c < 0 or self.service_level_c > 100:
            raise ValidationError(_("Service level for Item C must be in range 85 - 90 %"))

    #################################
    # MODEL FUNCTIONS
    #################################

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        set_param('reordering_rules_with_forecast.module_forecast_preparation', int(self.module_forecast_preparation))
        set_param('reordering_rules_with_forecast.module_forecast_preparation_with_mrp',
                  int(self.module_forecast_preparation_with_mrp))

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(
            module_forecast_preparation=get_param(
                'reordering_rules_with_forecast.module_forecast_preparation', '0') == '1',
            module_forecast_preparation_with_mrp=get_param(
                'reordering_rules_with_forecast.module_forecast_preparation_with_mrp', '0') == '1',
        )
        return res
