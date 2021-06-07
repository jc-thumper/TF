# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models

from odoo.addons.si_core.utils.database_utils import get_all_timezone
from odoo.addons.si_core.utils.datetime_utils import DEFAULT_TIMEZONE

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    ###############################
    # FIELDS
    ###############################
    timezone = fields.Selection(get_all_timezone(), string='Time Zone', default=DEFAULT_TIMEZONE,
                                compute='_compute_timezone', inverse='_inverse_timezone', store=False)
    default_warehouse = fields.Many2one('stock.warehouse', store=False, compute="_compute_default_warehouse")

    ###############################
    # COMPUTE FUNCTIONS
    ###############################
    @api.depends('partner_id')
    def _compute_timezone(self):
        for record in self:
            record.timezone = record.partner_id.tz or DEFAULT_TIMEZONE

    def _compute_default_warehouse(self):
        for company in self:
            warehouses_id = None
            try:
                company_id = company.id
                if company_id:
                    warehouses_id = self.env['stock.warehouse'] \
                        .search([('company_id', '=', company_id)], order='sequence asc', limit=1)
                else:
                    _logger.warning('Having some errors when initial the default warehouse', exc_info=True)
            except Exception:
                _logger.warning('Having some errors when initial the default warehouse', exc_info=True)
            company.default_warehouse = warehouses_id

    ###############################
    # INVERSE FIELDS
    ###############################
    def _inverse_timezone(self):
        for record in self:
            record.partner_id.tz = record.timezone or DEFAULT_TIMEZONE
