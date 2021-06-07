# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang


class AccountBatchDepositUSA(models.Model):
    _inherit = 'account.batch.payment'

    fund_line_ids = fields.One2many('account.batch.deposit.fund.line', 'batch_deposit_id')

    state = fields.Selection([('draft', 'New'), ('sent', 'Sent'), ('reconciled', 'Reconciled')], copy=False,
                             compute='_compute_state', store=True)

    @api.depends('payment_ids.state', 'fund_line_ids.bank_reconciled')
    def _compute_state(self):
        """
        By default of Odoo, state of batch payment = 'reconciled' <=> states of all payments = 'reconciled'.
        If we set to draft/cancel 1 payment, batch payment still keep the old state. (in def write(vals) of account.payment).
        But in USA, we add Adjustment, so need to check them to calculate state of batch payment.
        """
        for record in self:
            state = 'draft'

            if record.payment_ids:
                payment_states = record.payment_ids.mapped('state')
                # If state of at least 1 payment is 'draft' or 'posted', state of batch payment = 'draft'
                if 'draft' in payment_states or 'posted' in payment_states:
                    state = 'draft'
                # If no 'draft' or 'posted' payment, and at least 1 payment is 'sent', state of batch payment = 'sent'
                elif 'sent' in payment_states:
                    state = 'sent'
                # If all payments are reconciled, state of batch payment = above temporary_state
                else:
                    state = 'reconciled'

            if False in record.fund_line_ids.mapped('bank_reconciled') and state == 'reconciled':
                state = 'sent'

            record.state = state

    @api.constrains('amount')
    def _check_deposit_amount(self):
        for record in self:
            if record.amount < 0:
                raise ValidationError(_("Batch Deposit amount cannot be negative."))

    @api.depends('payment_ids', 'journal_id', 'fund_line_ids')
    def _compute_amount(self):
        """
        Call super to calculate the total of all payment lines.
        Then add the total of fund lines.
        """
        super(AccountBatchDepositUSA, self)._compute_amount()

        for record in self:
            company_currency = record.journal_id.company_id.currency_id or self.env.company.currency_id
            journal_currency = record.journal_id.currency_id or company_currency
            amount = 0
            for line in record.fund_line_ids:
                line_currency = line.currency_id or company_currency
                if line_currency == journal_currency:
                    amount += line.amount
                else:
                    # Note : this makes record.date the value date, which IRL probably is the date of the reception by the bank
                    amount += line_currency.with_context({'date': record.payment_date}).compute(line.amount, journal_currency)

            record.amount += amount

    def get_batch_payment_aml(self):
        """
        Get all account.move.line in batch payments, include payments and adjustments.
        :return: aml_ids
        """
        aml_ids = self.env['account.move.line']
        for record in self:
            for payment in record.payment_ids:
                journal_accounts = [payment.journal_id.default_debit_account_id.id,
                                    payment.journal_id.default_credit_account_id.id]
                aml_ids |= payment.move_line_ids.filtered(lambda r: r.account_id.id in journal_accounts)

            journal_accounts = [record.journal_id.default_debit_account_id.id, record.journal_id.default_credit_account_id.id]
            for line in record.fund_line_ids:
                aml_ids |= line.get_aml_adjustments(journal_accounts)

        return aml_ids

    def _get_batch_info_for_review(self):
        """
        Used to get info of this batch payment (except which has been reviewed (temporary_reconciled = True)).
        :return: dictionary of type, amount, amount_journal_currency, amount_payment_currency, journal_id
        """
        def get_amount(rec, currency):
            if currency == journal_currency:
                return rec.amount
            return currency._convert(rec.amount, journal_currency, self.journal_id.company_id, self.date or fields.Date.today())

        self.ensure_one()
        # Copy from account_batch_payment/account_batch_payment.
        company_currency = self.journal_id.company_id.currency_id or self.env.company.currency_id
        journal_currency = self.journal_id.currency_id or company_currency
        amount = self.amount

        for payment in self.payment_ids.filtered('has_been_reviewed'):
            payment_currency = payment.currency_id or company_currency
            amount -= get_amount(payment, payment_currency)

        for line in self.fund_line_ids.filtered('has_been_reviewed'):
            line_currency = line.currency_id or company_currency
            amount -= get_amount(line, line_currency)

        # Copy from account_batch_payment/widget_reconciliation.
        amount_journal_currency = formatLang(self.env, amount, currency_obj=journal_currency)
        amount_payment_currency = False
        payment_ids = self.payment_ids.filtered(lambda r: not r.has_been_reviewed)
        fund_line_ids = self.fund_line_ids.filtered(lambda r: not r.has_been_reviewed)
        if payment_ids and all(p.currency_id != journal_currency and p.currency_id == payment_ids[0].currency_id for p in payment_ids):
            amount_payment_currency = sum(p.amount for p in payment_ids) + sum(line.amount for line in fund_line_ids)
            amount_payment_currency = formatLang(self.env, amount_payment_currency, currency_obj=payment_ids[0].currency_id or company_currency)

        return {
            'type': self.batch_type,    # To filter in review screen.
            'amount': amount,
            'amount_str': amount_journal_currency,
            'amount_currency_str': amount_payment_currency,
            'journal_id': self.journal_id.id
        }

    def open_fund_entries(self):
        self.ensure_one()
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.fund_line_ids.mapped('account_move_id').ids)],
        }

    def write(self, vals):
        # If any account.move.line in this batch payment is not reconciled, remove state=reconciled out of vals.
        if vals.get('state', False) == 'reconciled':
            for record in self:
                aml_ids = record.get_batch_payment_aml().filtered(lambda r: not r.bank_reconciled)
                if aml_ids:
                    vals.pop('state')

        return super(AccountBatchDepositUSA, self).write(vals)


class BatchDepositFundLine(models.Model):
    _name = 'account.batch.deposit.fund.line'
    _description = 'Batch Payment Fund Line'

    partner_id = fields.Many2one('res.partner', 'Customer')
    account_id = fields.Many2one('account.account', 'Account')
    communication = fields.Char('Description')
    payment_date = fields.Date('Date')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary('Amount')
    account_move_id = fields.Many2one('account.move')
    batch_deposit_id = fields.Many2one('account.batch.payment', ondelete="cascade")

    # Technical fields
    has_been_reviewed = fields.Boolean(string='Have been reviewed?', compute='_compute_bank_reconciled', store=True, copy=False)
    bank_reconciled = fields.Boolean(string='Have been reconciled?', compute='_compute_bank_reconciled', store=True, copy=False)

    @api.depends('account_move_id', 'account_move_id.line_ids.bank_reconciled', 'account_move_id.line_ids.statement_line_id')
    def _compute_bank_reconciled(self):
        for record in self:
            aml_ids = record.get_aml_adjustments()
            bank_reconciled = has_been_reviewed = False
            if aml_ids:
                bank_reconciled = True in aml_ids.mapped('bank_reconciled')
                has_been_reviewed = bool(aml_ids.filtered('statement_line_id'))
            record.bank_reconciled = bank_reconciled
            record.has_been_reviewed = has_been_reviewed

    def _get_account_side(self, journal_id, amount):
        """
        Get account to post JE for Adjustments, based on sign of amount and type of batch payment.
            - Customer Batch Payment (type=inbound): amount > 0 => debit, amount < 0 => credit.
            - Vendor Batch Payment (type=outbound): amount > 0 => credit, amount < 0 => debit.
        :param journal_id:
        :param amount:
        :return: debit_account, credit_account
        """
        payment_type = self.batch_deposit_id.batch_type
        if payment_type == 'inbound' and amount >= 0 or payment_type == 'outbound' and amount <= 0:
            debit_account = journal_id.default_debit_account_id
            credit_account = self.account_id
        else:
            debit_account = self.account_id
            credit_account = journal_id.default_credit_account_id

        return debit_account, credit_account

    def get_aml_adjustments(self, journal_accounts=None):
        """
        Get account.move.line record posted by Adjustments, which is used in Reviewed screen and Reconciliation screen
        :param journal_accounts:
        """
        self.ensure_one()
        journal_accounts = journal_accounts or [self.batch_deposit_id.journal_id.default_debit_account_id.id,
                                                self.batch_deposit_id.journal_id.default_credit_account_id.id]
        sign = 1 if self.batch_deposit_id.batch_type == 'inbound' else -1
        return self.account_move_id.line_ids.filtered(lambda r: r.account_id.id in journal_accounts and
                                                                (0 < sign*self.amount == r.debit or 0 < -sign*self.amount == r.credit))

    def _create_account_move(self):
        """
        Create JE when users create new adjustment lines.
        """
        journal_id = self.batch_deposit_id.journal_id
        reference_text = self.communication or self.batch_deposit_id.display_name + ' Adjustment'

        debit_account, credit_account = self._get_account_side(journal_id, self.amount)

        new_account_move = self.env['account.move'].create({
            'journal_id': journal_id.id,
            'line_ids': [(0, 0, {
                'partner_id': self.partner_id.id if self.partner_id else False,
                'account_id': debit_account.id,
                'debit': abs(self.amount),
                'credit': 0,
                'date': self.payment_date,
                'name': reference_text,
                'is_fund_line': True,
            }), (0, 0, {
                'partner_id': self.partner_id.id if self.partner_id else False,
                'account_id': credit_account.id,
                'debit': 0,
                'credit': abs(self.amount),
                'date': self.payment_date,
                'name': reference_text,
                'is_fund_line': True,
            })],
            'date': self.payment_date,
            'ref': reference_text,
        })
        self.account_move_id = new_account_move
        new_account_move.post()

    @api.onchange('payment_date', 'partner_id', 'account_id', 'communication', 'amount')
    def _onchange_validation(self):
        for record in self:
            if record.account_move_id:
                raise ValidationError(_('A journal entry has been created for this line. '
                                        'If you want to update anything, '
                                        'please delete this line and create a new one instead.'))

    @api.model
    def create(self, vals):
        res = super(BatchDepositFundLine, self).create(vals)
        res._create_account_move()
        return res

    def unlink(self):
        self.mapped('account_move_id').button_draft()
        self.write({'account_move_id': [(5, 0, 0)]})
        return super(BatchDepositFundLine, self).unlink()
