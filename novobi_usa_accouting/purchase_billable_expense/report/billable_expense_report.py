# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class BillableExpenseReport(models.AbstractModel):
    _inherit = 'billable.expense.report'

    filter_include_po = True

    def open_purchase_expense(self, options, params=None):
        if not params:
            params = {}
        ctx = self.env.context.copy()
        ctx.pop('id', '')
        expense_id = params.get('id')
        document = params.get('object', 'purchase.order')
        if expense_id:
            expense = self.env['billable.expenses'].browse(expense_id)
            purchase_id = expense.purchase_id.id
            view_id = self.env['ir.model.data'].get_object_reference('purchase', 'purchase_order_form')[1]
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'tree',
                'views': [(view_id, 'form')],
                'res_model': document,
                'view_id': view_id,
                'res_id': purchase_id,
                'context': ctx,
            }
