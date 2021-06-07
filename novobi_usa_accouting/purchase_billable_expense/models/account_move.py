from odoo import models, fields


class AccountMoveUSA(models.Model):
    _inherit = 'account.move'

    def _assign_billable_expense(self):
        """
        Override to get billable expenses from Purchase Order, or create new ones.
        """
        self.ensure_one()
        bill_line_ids = self.billable_expenses_ids.mapped('bill_line_id')
        expense_env = self.env['billable.expenses'].sudo()

        # For all bill lines that have not been set billable expense:
        for line in self.invoice_line_ids - bill_line_ids:
            # If the purchase order line linked to it has been assigned billable expense -> Link current bill and bill line.
            if line.purchase_line_id and line.purchase_line_id.billable_expenses_ids:
                line.purchase_line_id.billable_expenses_ids.write({
                    'bill_id': self.id,
                    'bill_line_id': line.id
                })
            # Create new billable expense and link it to current bill/bill line.
            else:
                expense_env.create({
                    'bill_id': self.id,
                    'bill_line_id': line.id,
                    'description': line.name,
                    'amount': line.price_subtotal,
                    'bill_date': self.invoice_date
                })

    def action_post(self):
        """
        Inherit to automatically assign billable expenses to current bill (User does not have to click on button Assign)
        """
        super(AccountMoveUSA, self).action_post()
        for record in self.filtered(lambda r: r.type == 'in_invoice'):
            record._assign_billable_expense()

