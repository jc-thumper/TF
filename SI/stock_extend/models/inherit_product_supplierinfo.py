# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    ####################
    # MODEL FUNCTIONS
    ####################

    @api.model
    @api.returns('self',
                 upgrade=lambda self, value, args, offset=0, limit=None, order=None,
                                count=False: value if count else self.browse(value),
                 downgrade=lambda self, value, args, offset=0, limit=None, order=None,
                                  count=False: value if count else value.ids)
    def search(self, args, offset=0, limit=None, order=None, count=False):
        ctx = self._context
        if 'order_display' in ctx:
            order = ctx['order_display']

        res = super(SupplierInfo, self).search(args, offset=offset, limit=limit, order=order, count=count)
        return res
