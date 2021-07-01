# -*- coding: utf-8 -*-

import logging

from datetime import datetime
from psycopg2._psycopg import AsIs

from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.addons.si_core.utils import datetime_utils
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

_logger = logging.getLogger(__name__)


class InheritWarehouseOrderPoint(models.Model):
    """
    This model override create function
    """
    _name = 'stock.warehouse.orderpoint'
    _inherit = ['stock.warehouse.orderpoint', 'mail.thread', 'mail.activity.mixin', 'portal.mixin']

    safety_stock = fields.Float(
        'Safety Stock', digits='Product Unit of Measure', required=True,
        help="An additional quantity of an item held in the inventory to reduce the "
             "risk that the item will be out of stock.")

    def write(self, values):
        if self._valid_values_to_write(values):
            if values.get('product_min_qty', False) or values.get('product_max_qty', False):
                msg = "<b>Updated information in reordering rule.</b><ul>"
                msg += "<li>" + _("Min Quantity") + ": %s -> %s" % (
                    self.product_min_qty, values.get('product_min_qty', self.product_min_qty))
                msg += "<li>" + _("Max Quantity") + ": %s -> %s" % (
                    self.product_max_qty, values.get('product_max_qty', self.product_max_qty))
                self.message_post(body=msg)
            return super(InheritWarehouseOrderPoint, self).write(values)

    @api.model
    def create(self, vals):
        if self._valid_values_to_write(vals):
            product_id = vals['product_id']
            company_id = vals['company_id']
            warehouse_id = vals['warehouse_id']
            location_id = vals['location_id']
            existing_wh = self.env['stock.warehouse.orderpoint']\
                .search([('product_id', '=', product_id),
                         ('company_id', '=', company_id),
                         ('warehouse_id', '=', warehouse_id),
                         ('location_id', '=', location_id)])
            if existing_wh:
                raise UserError(_('This app just allow user create only one Reordering Rule '
                                  'for a product in each warehouse.'))
            new_rule = super(InheritWarehouseOrderPoint, self).create(vals)

            RRwF_model = self.env['reordering.rules.with.forecast']
            if not (self._context.get('not_create_rrwf') and self._context.get('rrwf_id')):
                rec_rules = RRwF_model\
                    .search([('product_id', '=', product_id),
                             ('company_id', '=', company_id),
                             ('warehouse_id', '=', warehouse_id),
                             ('location_id', '=', location_id)])
            else:
                rec_rules = RRwF_model.search([('id', '=', self._context.get('rrwf_id'))])
            if rec_rules:
                for rec_rule in rec_rules:
                    rec_rule.write({'orderpoint_id': new_rule.id})
            elif not self._context.get('not_create_rrwf'):
                values = {
                    'product_id': product_id,
                    'company_id': company_id,
                    'warehouse_id': warehouse_id,
                    'location_id': location_id,
                    'orderpoint_id': new_rule.id
                }
                RRwF_model.create(values)
            return new_rule

    def _valid_values_to_write(self, values):
        """

        :param values:
        :return:
        :rtype: bool
        """
        if values.get('product_min_qty', None) is not None and values.get('product_max_qty', None) is not None:
            if values.get('product_min_qty') > values.get('product_max_qty'):
                raise UserError(_("You can not set New Minimum Quantity greater than New Maximum Quantity"))
        elif values.get('product_min_qty', None) is not None:
            for rule in self:
                if rule.product_max_qty < values.get('product_min_qty'):
                    raise UserError(_("You can not set New Minimum Quantity greater than current Maximum Quantity"))
        elif values.get('product_max_qty', None) is not None:
            for rule in self:
                if rule.product_min_qty > values.get('product_max_qty'):
                    raise UserError(_("You can not set New Maximum Quantity less than current Minimum Quantity"))
        return True
