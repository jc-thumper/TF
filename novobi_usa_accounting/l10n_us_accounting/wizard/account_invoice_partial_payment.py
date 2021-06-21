# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import Warning
from ..utils.utils import has_multi_currency_group


class PartialPayment(models.TransientModel):
    _name = 'account.invoice.partial.payment'
    _description = 'Partial Payment'

    currency_id = fields.Many2one('res.currency', readonly=True)
    amount = fields.Monetary('Amount')
    invoice_id = fields.Many2one('account.move')
    move_line_id = fields.Many2one('account.move.line')

    have_same_currency = fields.Boolean(compute='_get_have_same_currency')

    @api.depends('invoice_id', 'move_line_id')
    def _get_have_same_currency(self):
        for record in self:
            have_same_currency = False
            if record.invoice_id and record.move_line_id:
                # TODO: change it to payment's currency instead
                move_line_currency = record.move_line_id.currency_id if record.move_line_id.currency_id \
                    else self.env.user.company_id.currency_id
                if record.invoice_id.currency_id.id == move_line_currency.id:
                    have_same_currency = True
            record.have_same_currency = have_same_currency

    @api.model
    def default_get(self, fields):
        res = super(PartialPayment, self).default_get(fields)

        invoice_id = self.env['account.move'].browse(self.env.context.get('invoice_id'))
        move_line_id = self.env['account.move.line'].browse(self.env.context.get('credit_aml_id'))

        res.update({
            'invoice_id': self.env.context.get('invoice_id'),
            'move_line_id': self.env.context.get('credit_aml_id'),
            'currency_id': invoice_id.currency_id.id
        })

        amount_due = invoice_id.amount_residual

        if move_line_id.currency_id and move_line_id.currency_id == invoice_id.currency_id:
            payment_amount = abs(move_line_id.amount_residual_currency)
        else:
            currency = move_line_id.company_id.currency_id
            payment_amount = currency._convert(abs(move_line_id.amount_residual), invoice_id.currency_id, invoice_id.company_id,
                                               move_line_id.date or fields.Date.today())

        # payment_amount = abs(move_line_id.amount_residual)
        if amount_due < payment_amount:
            res['amount'] = amount_due
        else:
            res['amount'] = payment_amount
        return res


    def apply(self):
        payment_name = 'Credit Note/Payment'
        invoice_name = 'Invoice'
        if self.invoice_id.type == 'in_invoice':  # vendor bill
            invoice_name = 'Bill'
        elif self.invoice_id.type == 'out_refund':  # Customer Credit Note
            payment_name = 'Invoice'
            invoice_name = 'Credit Note'
        elif self.invoice_id.type == 'in_refund':  # Vendor Credit Note
            payment_name = 'Credit Note'
            invoice_name = 'Bill'

        if not self.have_same_currency:  # we don't need to validate the amount if they have different currency
            self.invoice_id.js_assign_outstanding_line(self.move_line_id.id)
        else:
            if self.amount <= 0:
                raise Warning(_('You entered an invalid value. Please make sure you enter a value is greater than 0.'))
            elif self.amount > abs(self.move_line_id.amount_residual):
                raise Warning(_('You entered a value that exceeds the amount of the %s' % payment_name))
            elif self.amount > self.invoice_id.amount_residual:
                raise Warning(_('You entered a value that exceeds the amount due of the %s' % invoice_name))

            self.invoice_id.with_context(partial_amount=self.amount).js_assign_outstanding_line(self.move_line_id.id)  # reconcile
        return True
