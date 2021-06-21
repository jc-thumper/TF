# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models, _
from odoo.tools import float_is_zero


class AccountMoveDeposit(models.Model):
    _inherit = 'account.move'

    is_deposit = fields.Boolean('Is a Deposit?')

    def _compute_payments_widget_to_reconcile_info(self):
        super(AccountMoveDeposit, self)._compute_payments_widget_to_reconcile_info()

        for move in self:
            info = json.loads(move.invoice_outstanding_credits_debits_widget)

            if move.state != 'posted' or move.invoice_payment_state != 'not_paid' or not move.is_invoice(
                    include_receipts=True):
                continue

            domain = [('account_id.reconcile', '=', True),
                      ('payment_id.is_deposit', '=', True),
                      '|', ('move_id.state', '=', 'posted'), '&', ('move_id.state', '=', 'draft'),
                      ('journal_id.post_at', '=', 'bank_rec'),
                      ('partner_id', '=', move.commercial_partner_id.id),
                      ('reconciled', '=', False), '|', ('amount_residual', '!=', 0.0),
                      ('amount_residual_currency', '!=', 0.0)]

            if move.is_inbound():
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                type_payment = _('Outstanding credits')
            else:
                domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                type_payment = _('Outstanding debits')

            if not info:
                info = {'title': '', 'outstanding': True, 'content': [], 'move_id': self.id}
            lines = self.env['account.move.line'].search(domain)

            currency_id = move.currency_id
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == move.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        currency = line.company_id.currency_id
                        amount_to_show = currency._convert(abs(line.amount_residual), move.currency_id, move.company_id,
                                                           line.date or fields.Date.today())
                    if float_is_zero(amount_to_show, precision_rounding=move.currency_id.rounding):
                        continue
                    info['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'payment_id': line.payment_id.id,
                        'digits': [69, move.currency_id.decimal_places],
                        'payment_date': fields.Date.to_string(line.date),
                    })
                info['title'] = type_payment
                info['type'] = self.type
                move.invoice_outstanding_credits_debits_widget = json.dumps(info)
                move.invoice_has_outstanding = True

    def js_assign_outstanding_line(self, credit_aml_id):
        self.ensure_one()
        credit_aml = self.env['account.move.line'].browse(credit_aml_id)
        if credit_aml.payment_id and credit_aml.payment_id.is_deposit:
            line_to_reconcile = self.env['account.move.line']
            for inv in self:
                line_to_reconcile += inv.line_ids.filtered(
                    lambda r: not r.reconciled and r.account_id.internal_type in ('payable', 'receivable'))

            register_payment_line = self._create_deposit_payment_entry(credit_aml, line_to_reconcile)

            if register_payment_line and line_to_reconcile:
                (register_payment_line + line_to_reconcile).reconcile()
        else:
            return super(AccountMoveDeposit, self).js_assign_outstanding_line(credit_aml_id)

    def _create_deposit_payment_entry(self, payment_line, invoice_lines):
        total_invoice_amount = abs(sum(invoice_lines.mapped('amount_residual')))
        amount = min(total_invoice_amount, abs(payment_line.amount_residual))

        if self.env.context.get('partial_amount', False):
            amount = self.env.context.get('partial_amount')

        if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
            return False

        company_id = payment_line.company_id
        journal_id = False
        if payment_line.debit > 0:
            journal_id = company_id.vendor_deposit_journal_id
        elif payment_line.credit > 0:
            journal_id = company_id.customer_deposit_journal_id
        if not journal_id:
            journal_id = self.env['account.journal'].search([('type', '=', 'general')], limit=1)

        debit_account, credit_account = self._get_account_side(payment_line, invoice_lines)
        reference = "Deposit to Payment"
        payment_id = payment_line.payment_id
        date = self.invoice_date

        new_account_move = self.env['account.move'].create({
            'journal_id': journal_id.id,
            'date': date,
            'ref': reference,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'is_deposit': True,
            'type': 'entry',
            'line_ids': [(0, 0, {
                'partner_id': payment_line.partner_id.id,
                'account_id': debit_account.id,
                'debit': amount,
                'credit': 0,
                'date': date,
                'name': reference,
            }), (0, 0, {
                'partner_id': self.partner_id.id if self.partner_id else False,
                'account_id': credit_account.id,
                'debit': 0,
                'credit': amount,
                'date': date,
                'name': reference,
            })],
        })
        new_account_move.post()

        (payment_line + new_account_move.line_ids.filtered(
            lambda l: l.account_id == payment_line.account_id)).reconcile()
        payment_id.write({'deposit_ids': [(4, new_account_move.id)]})

        return new_account_move.line_ids.filtered(lambda l: l.account_id.internal_type in ('payable', 'receivable'))

    def _get_account_side(self, payment_line, invoice_lines):
        invoice_line = invoice_lines[0]
        debit_account = payment_line.account_id if payment_line.credit > 0 else invoice_line.account_id
        credit_account = payment_line.account_id if payment_line.debit > 0 else invoice_line.account_id

        return debit_account, credit_account

    def _reconcile_deposit(self, deposits, invoice):
        # Helper function to reconcile deposit automatically when confirm Invoice/Bill
        for deposit in deposits:
            move_line = deposit.move_line_ids.filtered(lambda line: line.account_id.reconcile
                                                                    and line.account_id.internal_type != 'liquidity'
                                                                    and not line.reconciled)
            if move_line:
                invoice.js_assign_outstanding_line(move_line.id)

    def button_draft(self):
        """
        When we set an invoice/bill to draft, we want to delete all the linked Deposit JE
        so next time it will display the Deposit Payment
        """
        non_entry_ids = self.filtered(lambda x: x.type != 'entry')

        for move in non_entry_ids:
            line_ids = move.mapped('line_ids')
            # TODO: is there a better way to do this?
            all_lines = line_ids.mapped('matched_debit_ids.debit_move_id') + \
                        line_ids.mapped('matched_debit_ids.credit_move_id') + \
                        line_ids.mapped('matched_credit_ids.debit_move_id') + \
                        line_ids.mapped('matched_credit_ids.credit_move_id')
            deposit_move_ids = all_lines.filtered(lambda line: line.move_id.is_deposit).mapped('move_id')

            super(AccountMoveDeposit, move).button_draft()

            deposit_move_ids.filtered(lambda x: x.state == 'posted').button_draft()
            deposit_move_ids.with_context(force_delete=True).unlink()

        # Call super for other transactions
        super(AccountMoveDeposit, self - non_entry_ids).button_draft()


class AccountMoveLineDeposit(models.Model):
    _inherit = 'account.move.line'

    def remove_move_reconcile(self):
        """
        This function only handle the case when we remove deposit from Invoice.
        Deposit Payment: Bank & Deposit Account
        Deposit JE: Deposit Account & AR/AP Account -> this is "self"
        """
        rec_move_ids = self.env['account.partial.reconcile']
        partial_id = self.env.context.get('partial_id', False)

        # If the function is called from Set to draft in Payment or Account move, we don't care
        if not partial_id:
            return super(AccountMoveLineDeposit, self).remove_move_reconcile()

        for record in self:
            if record.move_id.is_deposit and not record.payment_id:
                # For a deposit JE, we have 2 partial.reconcile links
                # 1 linked with the Deposit payment, 1 linked with the Invoice
                for aml in record.move_id.line_ids:
                    rec_move_ids += aml.matched_debit_ids + aml.matched_credit_ids
                rec_move_ids.unlink()

                record.move_id.button_cancel()
                record.move_id.with_context(force_delete=True).unlink()
            else:
                # Call super for other transactions
                super(AccountMoveLineDeposit, record).remove_move_reconcile()
