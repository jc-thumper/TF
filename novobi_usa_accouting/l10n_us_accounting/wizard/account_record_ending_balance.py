# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError


class AccountRecordEndingBalance(models.TransientModel):
    _name = 'account.record.ending.balance'
    _description = 'Record Ending Balance'

    options = fields.Selection([
        ('create_purchase_receipt', 'Record a bill and pay now'),
        ('create_vendor_bill', 'Record a bill then pay later'),
        ('open_report', 'Do it later'),
    ], string='Status', default='create_purchase_receipt')

    bank_reconciliation_data_id = fields.Many2one('account.bank.reconciliation.data')
    currency_id = fields.Many2one('res.currency',
                                  readonly=True, default=lambda self: self.env.user.company_id.currency_id)
    ending_balance = fields.Monetary('Ending Balance')
    vendor_id = fields.Many2one('res.partner', domain=[('supplier_rank', '>', 0)])
    payment_journal_id = fields.Many2one('account.journal', domain=[('type', '=', 'bank')])

    @api.onchange('options')
    def _onchange_options(self):
        self.payment_journal_id = False

    def apply(self):
        self.ensure_one()
        options = self.options

        # Do it later
        if options == 'open_report':
            action = self.env.ref('l10n_us_accounting.action_bank_reconciliation_data_report_form').read()[0]
            action['res_id'] = self.bank_reconciliation_data_id.id
            return action

        balance = -self.ending_balance
        vendor_id = self.vendor_id
        journal_id = self.bank_reconciliation_data_id.journal_id

        if not vendor_id:
            raise UserError(_('Please config the vendor of this journal "{}"'.format(journal_id.name)))
        if not journal_id.default_credit_account_id:
            raise UserError(_('Please config the account of this journal "{}"'.format(journal_id.name)))

        today = fields.Date.context_today(self)

        bill_id = self.env['account.move'].sudo().create({
            'type': 'in_invoice',
            'partner_id': vendor_id.id,
            'invoice_date': today,
            'invoice_line_ids': [(0, 0, {
                'name': 'Credit card expense',
                'account_id': journal_id.default_credit_account_id.id,
                'quantity': 1,
                'price_unit': balance
            })]
        })

        # Record a bill and pay now => Create payment and match with this bill.
        if options == 'create_purchase_receipt':
            # Post this vendor bill.
            bill_id.post()
            # Create new vendor payment and post it.
            journal_id = self.payment_journal_id
            payment_id = self.env['account.payment'].sudo().create({
                'journal_id': journal_id.id,
                'payment_method_id': journal_id.outbound_payment_method_ids and journal_id.outbound_payment_method_ids[0].id or False,
                'payment_date': today,
                'communication': bill_id.invoice_payment_ref or bill_id.ref or bill_id.name,
                'payment_type': 'outbound',
                'amount': balance,
                'partner_id': vendor_id.id,
                'partner_type': 'supplier',
            })
            payment_id.post()
            # Match bill with vendor payment.
            (payment_id.move_line_ids | bill_id.line_ids).filtered(lambda r: r.account_id.internal_type == 'payable').reconcile()

        # Open bill form in both case.
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move',
            'views': [[False, 'form']],
            'res_id': bill_id.id,
            'target': 'main'
        }
