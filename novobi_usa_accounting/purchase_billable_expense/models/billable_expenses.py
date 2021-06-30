# -*- coding: utf-8 -*-

from odoo import api, fields, models


class BillableExpenses(models.Model):
    _inherit = 'billable.expenses'

    purchase_id = fields.Many2one('purchase.order')
    purchase_line_id = fields.Many2one('purchase.order.line')  # expense created from a PO line

    @api.depends('purchase_id', 'bill_id')
    def _compute_company_id(self):
        """
        Override to get data from PO
        """
        for record in self:
            source = record.bill_id or record.purchase_id
            values = (source.name, source.partner_id, source.currency_id, source.company_id) if source else (False, False, False, False)

            record.source_document = values[0]
            record.supplier_id = values[1]
            record.currency_id = values[2]
            record.company_id = values[3]

    def _log_message_expense(self, vals):
        """
        Override to log note in PO
        """
        for record in self:
            msg = record._get_log_msg(vals)
            if record.bill_id:
                record.bill_id.message_post(body=msg, subtype='account_billable_expense.mt_billable_expense')
            if record.purchase_id:
                record.purchase_id.message_post(body=msg, subtype='account_billable_expense.mt_billable_expense')

    def get_expense_account(self):
        """
        Override to get account from product of purchase order lines.
        :return: account_id (int)
        """
        account = self._get_expense_account(self.mapped('purchase_line_id'))
        return account or super(BillableExpenses, self).get_expense_account()

    def unlink(self):
        """
        In case that we set a vendor bill to draft, removed the link between expenses that created
        from PO and this vendor bill (not delete so still keep it in PO), then delete the remaining expenses.
        """
        if self._context.get('unlink_bill', False):
            purchase_expense = self.filtered('purchase_id')
            purchase_expense.write({'bill_id': False})
            self -= purchase_expense
        return super(BillableExpenses, self).unlink()
