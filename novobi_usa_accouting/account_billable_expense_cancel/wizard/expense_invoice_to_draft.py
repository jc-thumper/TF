from odoo import models, fields, _


class ExpenseInvoiceToDraft(models.TransientModel):
    _inherit = 'button.draft.message'

    is_billable = fields.Boolean(related='move_id.is_billable')
    remove_expenses = fields.Boolean('Check if you want to remove all billable expenses from this invoice.', default=False)

    def button_set_to_draft(self):
        if self.remove_expenses:
            self = self.with_context(remove_expenses=True)
            
        super(ExpenseInvoiceToDraft, self).button_set_to_draft()
