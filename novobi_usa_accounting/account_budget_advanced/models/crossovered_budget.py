# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, fields


class CrossoveredBudget(models.Model):
    _inherit = 'crossovered.budget'

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    budget_type = fields.Selection([('profit', 'Profit and Loss'), ('balance', 'Balance Sheet')], default='profit')

    def update_budget_lines(self, dict):
        self.ensure_one()

        budget_lines = self.crossovered_budget_line
        updated_lines = []

        for key, value in dict.items():
            lines = budget_lines.filtered(lambda x: int(key) in x.general_budget_id.account_ids.ids).sorted(lambda x: x.date_from)
            updated_lines.extend([(1, line.id, {'planned_amount_entry': value[index]}) for index, line in enumerate(lines)])
        self.write({'crossovered_budget_line': updated_lines})
        return True

    def action_see_budget_report(self):
        name = self.name

        action_obj = self.sudo().env.ref('account_budget_advanced.action_usa_budget_report')
        action_obj['params'] = {'crossovered_budget_id': self.id}  # for refreshing the page
        action = action_obj.read()[0]

        action.update({
            'name': name,
            'display_name': name,
            'context': {'model': 'usa.budget.report', 'crossovered_budget_id': self.id}
        })
        return action


class BudgetPosition(models.Model):
    _inherit = 'account.budget.post'

    positive_account = fields.Boolean('Is this account positive?', default=True)


class BudgetLines(models.Model):
    _inherit = 'crossovered.budget.lines'

    planned_amount_entry = fields.Monetary('Planned Amount in Budget Entry',
                                           help="Amount in Budget Entry screen, "
                                                "the sign doesn't reflect if it's a revenue or cost.")
    positive_account = fields.Boolean('Is this account positive?', related='general_budget_id.positive_account')
    planned_amount = fields.Monetary(compute='_get_planned_amount', store=True, default=0)

    @api.depends('planned_amount_entry', 'positive_account')
    def _get_planned_amount(self):
        for record in self:
            record.planned_amount = record.planned_amount_entry if record.positive_account \
                else record.planned_amount_entry * -1