from odoo import api, fields, models


class ResPartnerUSA(models.Model):
    _inherit = 'res.partner'

    billable_expenses_ids = fields.One2many('billable.expenses', 'customer_id')

    def _get_related_commercial_partner(self):
        commercial_partner_id = self.mapped('commercial_partner_id')
        if not self or len(commercial_partner_id) != 1:
            return self

        return self.search([('commercial_partner_id', '=', commercial_partner_id.id)])

    def get_outstanding_expenses(self, options, company_ids, subcontact=False):
        """
        Called from billable expense report
        :param options: from account.reports
        :param company_ids: list of company id.
        :param subcontact:
            - False to use in Billable Expense report
            - True to find all expenses from parent and sub contact to apply in Invoice.
        :return: recordset of billable.expenses
        """
        partners = self if not subcontact else self._get_related_commercial_partner()
        return partners.mapped('billable_expenses_ids').filtered(lambda ex: ex.is_outstanding and ex.company_id.id in company_ids)
