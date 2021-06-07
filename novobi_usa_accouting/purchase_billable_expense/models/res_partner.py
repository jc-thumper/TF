from odoo import models, fields


class USResPartner(models.Model):
    _inherit = 'res.partner'

    def get_outstanding_expenses(self, options, company_ids, subcontact=False):
        """
        Inherit to use for both billable expense report, and in invoice to select only expenses which are linked to
        posted vendor bill.
        :param options: {} (from Invoice) or dictionary (from report)
        :param company_ids: list of company id
        :param subcontact:
            - False to use in Billable Expense report
            - True to find all expenses from parent and sub contact to apply in Invoice.
        :return: recordset of billable.expenses
        """
        expenses = super(USResPartner, self).get_outstanding_expenses(options, company_ids, subcontact)

        # For Billable Expense report: If uncheck filter `Include Purchase Orders`, remove all lines that are created
        # from PO, except the ones that have been added to bill already.
        if not options.get('include_po', True):
            return expenses.filtered(lambda r: not r.purchase_id or r.bill_id and r.bill_id.state == 'posted')

        # For button assign in Invoice: Only expenses which linked to Vendor Bill is able to be used.
        if not options:
            return expenses.filtered(lambda r: r.bill_id and r.bill_id.state == 'posted')

        return expenses
