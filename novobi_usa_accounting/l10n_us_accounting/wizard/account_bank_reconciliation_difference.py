# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, fields


class BankReconciliationDifference(models.TransientModel):
    _name = 'account.bank.reconciliation.difference'
    _description = 'Bank Reconciliation Difference'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    adjustment_date = fields.Date('Adjustment Date', default=fields.Date.context_today)
    reconciliation_discrepancies_account_id = fields.Many2one('account.account',
        'Reconciliation Discrepancies Account', related='company_id.reconciliation_discrepancies_account_id', readonly=False)
    bank_reconciliation_data_id = fields.Many2one('account.bank.reconciliation.data')

    def _get_account_side(self, journal_id, difference):
        self.ensure_one()

        debit_account = journal_id.default_credit_account_id if difference >= 0 \
            else self.reconciliation_discrepancies_account_id
        credit_account = self.reconciliation_discrepancies_account_id if difference >= 0 \
            else journal_id.default_debit_account_id

        return debit_account, credit_account

    def apply(self):
        self.ensure_one()

        # create journal entry
        difference = self.bank_reconciliation_data_id.difference
        journal_id = self.bank_reconciliation_data_id.journal_id

        debit_account, credit_account = self._get_account_side(journal_id, difference)

        new_account_move = self.env['account.move'].create({
            'journal_id': journal_id.id,
            'line_ids': [(0, 0, {
                    'account_id': debit_account.id,
                    'debit': abs(difference),
                    'credit': 0,
                    'date': self.adjustment_date,
                    'name': 'Reconciliation Discrepancy',
                    'bank_reconciled': True,
                }), (0, 0, {
                    'account_id': credit_account.id,
                    'debit': 0,
                    'credit': abs(difference),
                    'date': self.adjustment_date,
                    'name': 'Reconciliation Discrepancy',
                    'bank_reconciled': True,
                })],
            'date': self.adjustment_date,
            'ref': 'Reconciliation Discrepancy',
        })
        self.bank_reconciliation_data_id.discrepancy_entry_id = new_account_move  # so we can delete it when undo
        new_account_move.post()

        return self.bank_reconciliation_data_id.do_reconcile()
