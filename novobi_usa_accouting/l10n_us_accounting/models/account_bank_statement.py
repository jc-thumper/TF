# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from ..utils import bank_statement_line_utils

import logging
_logger = logging.getLogger(__name__)


class AccountBankStatementUSA(models.Model):
    _inherit = 'account.bank.statement'

    def button_journal_entries(self):
        # Show tree view of Journal Entry
        res = super().button_journal_entries()

        view_id = self.env.ref('account.view_move_tree').id
        res.update({'views': [(view_id, 'tree')],
                    'view_id': view_id})
        return res


class AccountBankStatementLineUSA(models.Model):
    _name = 'account.bank.statement.line'
    _inherit = ['account.bank.statement.line', 'mail.thread', 'mail.activity.mixin']

    # Override
    name = fields.Char(string='Description', track_visibility='onchange')
    date = fields.Date(track_visibility='onchange')
    partner_id = fields.Many2one(track_visibility='onchange')
    amount = fields.Monetary(track_visibility='onchange')

    # New fields
    transaction_type = fields.Selection([
        ('amount_paid', 'Send Money'),
        ('amount_received', 'Receive Money')
    ], string='Transaction Type', compute='_compute_transaction_type', store=True, readonly=True)

    status = fields.Selection([('open', 'Open'), ('confirm', 'Reviewed'), ('reconciled', 'Reconciled'), ('excluded', 'Excluded')],
                              string='Status', required=True, readonly=False, copy=False, default='open', track_visibility='onchange')

    # memo = fields.Char(string='Memo', default=lambda self: self._context.get('name'))

    # Technical fields
    check_number_cal = fields.Char('Check Number from Statement\'s name', compute='_compute_check_number_cal', store=True,
                                   help='Check number which is calculated from name of bank statement line, used to map with check number from account payment')

    @api.depends('name')
    def _compute_check_number_cal(self):
        for record in self:
            name = record.name
            record.check_number_cal = bank_statement_line_utils.extract_check_number(name) \
                if bank_statement_line_utils.is_check_statement(name) else False

    @api.depends('amount')
    def _compute_transaction_type(self):
        for record in self:
            record.transaction_type = 'amount_paid' if record.amount < 0 else 'amount_received'

    # @api.model
    # def create(self, values):
    #     values['memo'] = values.get('name', False)
    #     result = super(AccountBankStatementLineUSA, self).create(values)
    #     return result

    @api.model
    def update_historical_reconciliation_data(self):
        """
        Function to update values for historical bank reconciliation when installing new l10n_us_accounting.
        """
        _logger.info('========== STARTING UPDATING HISTORICAL DATA FOR BANK RECONCILIATION ==========')

        # Mark as reviewed and reconciled for account.move.line linked to BSL (Use Odoo OOTB's reconciliation)
        self.env['account.move.line'].search([('statement_line_id', '!=', False)]).write({
            'temporary_reconciled': True,
            'bank_reconciled': True
        })
        _logger.info('Update Bank Reconciled for account.move.line successfully!')

        # For BSL which has been reconciled, update its new status
        for statement in self.search([('journal_entry_ids', '!=', False)]):
            if False not in statement.journal_entry_ids.filtered('should_be_reconciled').mapped('bank_reconciled'):
                statement.status = 'reconciled'
            else:
                statement.status = 'confirm'
        _logger.info('Update Reviewed/Reconciled Status for account.bank.statement.line successfully!')

        # Uncheck match_partner to automatically match with all possible partners. This is from OOTB but USA does not use.
        self.env['account.reconcile.model'].search([]).write({'match_partner': False})
        _logger.info('Uncheck match_partner in all Bank Rules successfully!')

        _logger.info('========== FINISH UPDATING HISTORICAL DATA FOR BANK RECONCILIATION ==========')

    def _prepare_payment_vals(self, total):
        # Use Odoo's reconciliation form as our reviewed form.
        # So only set state of new payment account = 'posted', not 'reconciled'
        payment_vals = super(AccountBankStatementLineUSA, self)._prepare_payment_vals(total)
        payment_vals['state'] = 'posted'
        return payment_vals

    def button_cancel_reconciliation(self):
        # Override Odoo's, used to undo review bank statement lines.
        # Need to set status of bank statement lines back to 'open'
        aml_ids = self.mapped('journal_entry_ids')
        aml_ids.write({'temporary_reconciled': False})
        super(AccountBankStatementLineUSA, self).button_cancel_reconciliation()
        self.write({'status': 'open'})

    def action_exclude(self, exclude_ids=None):
        """
        To exclude bank statement lines, could be called directly or by using _rpc in reconciliation_model.js
        :param exclude_ids: list of bank statement lines id from args of _rpc
        """
        if exclude_ids:
            self = self.browse(exclude_ids)
        rec_ids = self.filtered(lambda r: r.status not in ['open', 'excluded'])
        if rec_ids:
            raise UserError(_('You cannot exclude any bank statement line which has been reviewed or reconciled.'))
        self.write({'status': 'excluded'})

    def action_undo_review(self):
        rec_ids = self.filtered(lambda r: r.status != 'confirm')
        if rec_ids:
            raise UserError(_('You cannot undo review any bank statement line which has not been reviewed.'))
        self.with_context(force_unlink=1).button_cancel_reconciliation()

        # If users using Invoice Matching, a payment is automatically created and its name is written to this bank
        # statement line, so we could not re-review after undo review.
        self.write({'move_name': False})

    def action_undo_exclude(self):
        rec_ids = self.filtered(lambda r: r.status != 'excluded')
        if rec_ids:
            raise UserError(_('You cannot undo exclude any bank statement line which has not been excluded.'))
        self.write({'status': 'open'})

    def action_review(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'bank_statement_reconciliation_view',
            'context': {'statement_line_ids': self.ids, 'company_ids': self.mapped('company_id').ids},
        }

    def button_view_journal_entries(self):
        # View Journal Entry in each BSL form view.
        view_id = self.env.ref('account.view_move_tree').id
        return {
            'name': _('Journal Entries'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'views': [(view_id, 'tree')],
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.mapped('journal_entry_ids').mapped('move_id').ids)],
        }
