# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, fields
from odoo.tools import float_compare
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.misc import formatLang
from datetime import datetime
from odoo.exceptions import Warning


class BankReconciliationData(models.Model):
    _name = 'account.bank.reconciliation.data'
    _description = 'Bank Reconciliation Data'
    _rec_name = 'statement_ending_date'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    journal_id = fields.Many2one('account.journal', 'Account')
    currency_id = fields.Many2one('res.currency', readonly=True, default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reconciled', 'Reconciled'),
    ], default='draft', string='State', required=True, copy=False)

    statement_beginning_date = fields.Date('Statement Beginning Date')
    statement_ending_date = fields.Date('Statement Ending Date')
    start_date = fields.Date('Start Date')
    reconcile_on = fields.Date('Reconcile On')
    beginning_balance = fields.Monetary('Beginning Balance')
    ending_balance = fields.Monetary('Ending Balance')

    previous_reconciliation_id = fields.Many2one('account.bank.reconciliation.data')

    # Data for report
    data_line_ids = fields.One2many('account.bank.reconciliation.data.line', 'bank_reconciliation_data_id')
    change_transaction_ids = fields.One2many('account.bank.reconciliation.data.line', 'bank_reconciliation_data_id',
                                             domain=[('is_cleared', '=', True), ('change_status', '!=', 'normal')])
    payments_cleared_ids = fields.One2many('account.bank.reconciliation.data.line', 'bank_reconciliation_data_id',
                                           domain=[('transaction_type', '=', 'payment'), ('is_cleared', '=', True)])
    deposits_cleared_ids = fields.One2many('account.bank.reconciliation.data.line', 'bank_reconciliation_data_id',
                                           domain=[('transaction_type', '=', 'deposit'), ('is_cleared', '=', True)])
    payments_uncleared_ids = fields.One2many('account.bank.reconciliation.data.line', 'bank_reconciliation_data_id',
                                           domain=[('transaction_type', '=', 'payment'), ('is_cleared', '=', False)])
    deposits_uncleared_ids = fields.One2many('account.bank.reconciliation.data.line', 'bank_reconciliation_data_id',
                                             domain=[('transaction_type', '=', 'deposit'), ('is_cleared', '=', False)])
    aml_ids = fields.Many2many('account.move.line')

    discrepancy_entry_id = fields.Many2one('account.move')
    difference = fields.Monetary('Adjustment')
    payments_cleared = fields.Monetary('Payments Cleared')
    deposits_cleared = fields.Monetary('Deposits Cleared')
    payments_uncleared = fields.Monetary('Uncleared Payments')  # Negative amount
    deposits_uncleared = fields.Monetary('Uncleared Deposits')
    register_balance = fields.Monetary('Register Balance')
    change_amount = fields.Monetary('Changes', compute='_compute_change_amount')
    payment_count = fields.Char()
    deposit_count = fields.Char()

    def _compute_change_amount(self):
        for record in self:
            record.change_amount = sum(line.amount_change for line in record.change_transaction_ids)

    @api.model
    def default_get(self, fields):
        defaults = super(BankReconciliationData, self).default_get(fields)

        if defaults.get('journal_id', False):
            journal_id = defaults['journal_id']

            draft_reconciliation = self.search([('journal_id', '=', journal_id), ('state', '=', 'draft')])
            if draft_reconciliation:
                return defaults

            previous_reconciliation = self.search([('journal_id', '=', journal_id), ('state', '=', 'reconciled')], order='id desc', limit=1)
            if previous_reconciliation:
                defaults['previous_reconciliation_id'] = previous_reconciliation.id
                defaults['beginning_balance'] = previous_reconciliation.ending_balance
                defaults['statement_beginning_date'] = previous_reconciliation.statement_ending_date

        return defaults

    def open_reconcile_screen(self):
        if self.env.context.get('edit_info', False):
            return True

        # we want to mark matched transactions when we create new record, not from undo
        #if self.env.context.get('start_reconciliation', False):
        #    self._mark_matched_transaction()

        action = self._get_reconciliation_screen(self.id)
        return action

    ############################
    #  MAIN FUNCTIONS
    ############################

    def action_print_report(self):
        return self.env.ref('l10n_us_accounting.account_bank_reconciliation_data_report').report_action(self)

    def check_difference_amount(self, aml_ids, difference, cleared_payments, cleared_deposits):
        self.ensure_one()
        self.write({
            'difference': difference,
            'payments_cleared': cleared_payments,
            'deposits_cleared': cleared_deposits,
            # 'aml_ids': [(6, 0, aml_ids)],
            'reconcile_on': datetime.today(),
        })

        if float_compare(difference, 0.0, precision_digits=2) != 0:  # difference != 0
            formatted_value = formatLang(self.env, 0.0, currency_obj=self.env.company.currency_id)
            return {
                'name': "Your difference isn't {} yet".format(formatted_value),
                'type': 'ir.actions.act_window',
                'res_model': 'account.bank.reconciliation.difference',
                'view_type': 'form',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'context': {'default_bank_reconciliation_data_id': self.id},
                'target': 'new',
            }
        return self.do_reconcile()

    def do_reconcile(self):
        self.ensure_one()

        # Mark AML and all reviewed bank statement lines as reconciled
        reconciled_items = self.aml_ids.filtered(lambda x: x.temporary_reconciled)
        reconciled_items.mark_bank_reconciled()

        # Create report
        self._create_report_line()
        payments_uncleared = - sum(record.amount for record in self.payments_uncleared_ids)
        deposits_uncleared = sum(record.amount for record in self.deposits_uncleared_ids)
        register_balance = self.ending_balance + payments_uncleared + deposits_uncleared
        payment_count = len(self.payments_cleared_ids)
        deposit_count = len(self.deposits_cleared_ids)
        self.write({'payments_uncleared': payments_uncleared,
                    'deposits_uncleared': deposits_uncleared,
                    'register_balance': register_balance,
                    'payment_count': '(' + str(payment_count) + ')',
                    'deposit_count': '(' + str(deposit_count) + ')',
                    'state': 'reconciled'})

        if self.journal_id.is_credit_card and self.ending_balance < 0:
            action = self.env.ref('l10n_us_accounting.action_record_ending_balance').read()[0]
            action['hide_close_btn'] = True
            action['context'] = {'default_ending_balance': self.ending_balance,
                                 'default_bank_reconciliation_data_id': self.id,
                                 'default_vendor_id': self.journal_id.partner_id and self.journal_id.partner_id.id or False}
            return action

        # Reset temporary_reconciled for next reconciliation
        self._reset_transactions()

        # Redirect to report form, main to clear breadcrumb
        action = self.env.ref('l10n_us_accounting.action_bank_reconciliation_data_report_form').read()[0]
        action['res_id'] = self.id
        return action

    def undo_last_reconciliation(self):
        if not self.previous_reconciliation_id:
            raise Warning(_('There are no previous reconciliations to undo.'))

        self._undo()

        # Return screen of previous reconciliation
        action = self._get_reconciliation_screen(self.previous_reconciliation_id.id)

        # Delete the newly created record
        self.unlink()
        return action

    def _undo(self):
        """
        Undo last reconciliation
        """
        self.ensure_one()

        # Reset some fields
        prev_id = self.previous_reconciliation_id
        prev_id.with_context(undo_reconciliation=True).write({
            'state': 'draft',
            'ending_balance': self.ending_balance,
            'statement_ending_date': self.statement_ending_date,
            'data_line_ids': [(5,)]
        })

        # Un-mark reconciled, don't change temporary_reconciled so they can still be marked in reconciliation screen
        prev_id.aml_ids.filtered(lambda x: x.bank_reconciled).undo_bank_reconciled()

        # Reset status of all reconciled bank statement lines back to 'confirm'
        prev_id.aml_ids.mapped('statement_line_id').filtered(lambda x: x.status == 'reconciled').write({'status': 'confirm'})

        # Reverse discrepancy entry, if any
        if prev_id.discrepancy_entry_id:
            reverse_move_id = prev_id.discrepancy_entry_id.with_context(discrepancy_entry=True)._reverse_moves(cancel=True).ids
            reverse_move = self.env['account.move'].browse(reverse_move_id)
            reverse_move.line_ids.mark_bank_reconciled()

    def close_without_saving(self):
        self.ensure_one()
        self._reset_transactions()
        super(BankReconciliationData, self).unlink()
        return self.env.ref('account.open_account_journal_dashboard_kanban').read()[0]

    ############################
    #  HELPER FUNCTIONS
    ############################
    def get_popup_form_id(self):
        """
        Use for Edit Info button in reconciliation screen
        """
        return self.env.ref('l10n_us_accounting.bank_reconciliation_data_popup_form').id

    def _get_reconciliation_screen(self, data_id):
        """
        Helper function to return action given bank_data_id
        """
        action_obj = self.env.ref('l10n_us_accounting.action_usa_bank_reconciliation')
        action_obj['params'] = {'bank_reconciliation_data_id': data_id}
        action = action_obj.read()[0]
        action['context'] = {'model': 'usa.bank.reconciliation',
                             'bank_reconciliation_data_id': data_id}
        return action

    def _create_report_line(self):
        self.ensure_one()
        line_env = self.env['account.bank.reconciliation.data.line'].sudo()

        for line in self.aml_ids:
            line_env.create({
                'aml_id': line.id,
                'name': line.move_id.name,
                'date': line.date,
                'memo': line.name,
                'check_number': line.payment_id.check_number if line.payment_id and line.payment_id.check_number else '',
                'payee_id': line.partner_id.id if line.partner_id else False,
                'amount': line.credit if line.credit > 0 else line.debit,
                'amount_signed': line.credit if line.credit > 0 else (line.debit * -1),
                'transaction_type': 'payment' if line.credit > 0 else 'deposit',
                'is_cleared': line.temporary_reconciled,
                'bank_reconciliation_data_id': self.id,
            })

    def _reset_transactions(self, old_date=None, new_date=None):
        """ Reset transactions
        Transactions that are not really reconciled but temporarily
        Used when reconcile, close without saving & change ending date
        Only reset transactions within a time frame (change ending date)
        """
        account_ids = [self.journal_id.default_debit_account_id.id,
                       self.journal_id.default_credit_account_id.id]
        domain_date = [('date', '>', old_date), ('date', '<=', new_date)] if old_date else []

        domain_aml = [('account_id', 'in', account_ids), ('bank_reconciled', '=', False)]
        domain_aml.extend(domain_date)
        aml_ids = self.env['account.move.line'].search(domain_aml)
        aml_ids.filtered(lambda r: not r.statement_line_id and r.temporary_reconciled).write({'temporary_reconciled': False})
        aml_ids.filtered(lambda r: r.statement_line_id and not r.temporary_reconciled).write({'temporary_reconciled': True})

    ############################
    #  CRUD
    ############################

    def write(self, vals):
        # if it's from Undo, we want to keep the same state of transactions
        if vals.get('statement_ending_date', False) and not self.env.context.get('undo_reconciliation', False):
            new_date = datetime.strptime(vals.get('statement_ending_date'), DEFAULT_SERVER_DATE_FORMAT).date()
            for record in self:
                old_date = record.statement_ending_date

                if new_date > old_date:
                    record._reset_transactions(old_date, new_date)

        return super(BankReconciliationData, self).write(vals)


class BankReconciliationDataLine(models.Model):
    _name = 'account.bank.reconciliation.data.line'
    _description = 'Bank Reconciliation Data Line'

    name = fields.Char('Number')
    date = fields.Date('Date')
    check_number = fields.Char('Checks No')
    memo = fields.Char('Memo')
    payee_id = fields.Many2one('res.partner', 'Payee')
    amount = fields.Monetary('Amount')
    amount_signed = fields.Monetary('Amount Signed')
    currency_id = fields.Many2one('res.currency', readonly=True, default=lambda self: self.env.company.currency_id)
    transaction_type = fields.Selection([('payment', 'Payment'), ('deposit', 'Deposit')])
    is_cleared = fields.Boolean('Cleared?')
    bank_reconciliation_data_id = fields.Many2one('account.bank.reconciliation.data', ondelete='cascade')
    # Change Section
    amount_change = fields.Monetary('Amount Change', compute='compute_change_status', store=True)
    current_amount = fields.Monetary('Current Amount', compute='compute_change_status', store=True)
    change_status = fields.Selection(
        [('normal', 'Normal'), ('canceled', 'Canceled'), ('deleted', 'Deleted'), ('changed', 'Amount Changed')],
        default='normal', compute='compute_change_status', store=True)
    has_been_canceled = fields.Boolean()
    aml_id = fields.Many2one('account.move.line')
    batch_id = fields.Many2one('account.batch.payment')

    @api.depends('aml_id', 'aml_id.move_id.state')
    def compute_change_status(self):
        for record in self:
            change_status = current_amount = amount_change = False
            if not record.aml_id:
                change_status = 'deleted'
                current_amount = 0
                amount_change = record.amount_signed
            elif (record.aml_id and record.aml_id.move_id.state == 'draft') or record.has_been_canceled:
                change_status = 'canceled'
                current_amount = 0
                amount_change = record.amount_signed
                record.has_been_canceled = True
            else:
                change_status = 'normal'

            record.change_status = change_status
            record.current_amount = current_amount
            record.amount_change = amount_change
