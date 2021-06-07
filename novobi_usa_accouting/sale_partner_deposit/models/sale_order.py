# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SalesOrder(models.Model):
    _inherit = 'sale.order'

    deposit_ids = fields.One2many('account.payment', 'sale_deposit_id', string='Deposits',
                                  domain=[('state', 'not in', ['draft', 'cancelled'])])
    deposit_count = fields.Integer('Deposit Count', compute='_get_deposit_total', store=True)
    deposit_total = fields.Monetary(string='Total Deposit', compute='_get_deposit_total', store=True)
    remaining_total = fields.Monetary(string='Net Total', compute='_get_deposit_total', store=True)

    @api.depends('amount_total', 'deposit_ids', 'deposit_ids.state')
    def _get_deposit_total(self):
        for order in self:
            deposit_total = sum(deposit.amount for deposit in order.deposit_ids)

            order.update({
                'deposit_total': deposit_total,
                'deposit_count': len(order.deposit_ids),
                'remaining_total': order.amount_total - deposit_total,
            })

    def action_view_deposit(self):
        action = self.env.ref('account_partner_deposit.action_account_payment_customer_deposit').read()[0]
        action['domain'] = [('id', 'in', self.deposit_ids.ids)]
        return action

    def _create_invoices(self, grouped=False, final=False):
        invoices = super(SalesOrder, self)._create_invoices(grouped, final)

        if self.env.context.get('validate_invoice', False):
            invoices.action_post()

        return invoices
