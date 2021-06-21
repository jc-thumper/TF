# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, fields
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime
from odoo.exceptions import UserError


class USABankReconciliation(models.AbstractModel):
    _inherit = 'account.report'
    _name = 'usa.bank.reconciliation'
    _description = 'Bank Reconciliation'

    def _get_templates(self):
        templates = super(USABankReconciliation, self)._get_templates()
        templates['line_template'] = 'l10n_us_accounting.line_template_usa_bank_reconciliation'
        templates['main_template'] = 'l10n_us_accounting.template_usa_bank_reconciliation'
        return templates

    def _get_columns_name(self, options):
        # Payment is Credit. Deposit is Debit.
        return [
            {},
            {'name': _('Date'), 'class': 'date'},
            {'name': _('Payee')},
            {'name': _('Memo')},
            {'name': _('Check Number')},
            {'name': _('Payment'), 'class': 'number'},
            {'name': _('Deposit'), 'class': 'number'},
            {'name': _('Reconcile')},
        ]

    def _get_aml(self, bank_reconciliation_data_id):
        """
        Get all account.move.line except in batch payments to show in Reconciliation screen.
        :param bank_reconciliation_data_id:
        :return: aml_ids
        """
        account_ids = [bank_reconciliation_data_id.journal_id.default_debit_account_id.id,
                       bank_reconciliation_data_id.journal_id.default_credit_account_id.id]

        # bank_reconciled is our new field.
        # an account move line is considered reconciled if bank_reconciled is checked.
        aml_ids = self.env['account.move.line'].search([
            ('account_id', 'in', account_ids),
            ('date', '<=', bank_reconciliation_data_id.statement_ending_date),
            ('bank_reconciled', '=', False),
            ('is_fund_line', '=', False),
            ('move_id.state', '=', 'posted'),
            '|', ('payment_id', '=', False), '&', ('payment_id', '!=', False), ('payment_id.batch_payment_id', '=', False)
        ])
        return aml_ids

    def _get_batch_payment_aml(self, bank_reconciliation_data_id):
        """
        Get all account.move.line in batch payments, include payments and adjustments.
        :param bank_reconciliation_data_id:
        :return: aml_ids
        """
        journal_id = bank_reconciliation_data_id.journal_id

        batch_ids = self.env['account.batch.payment'].search([
            ('journal_id', '=', journal_id.id),
            ('state', '!=', 'reconciled'),
            ('date', '<=', bank_reconciliation_data_id.statement_ending_date)
        ])

        return batch_ids.get_batch_payment_aml().filtered(lambda r: not r.bank_reconciled)

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        bank_reconciliation_data_id = self._get_bank_reconciliation_data_id()

        aml_ids = self._get_aml(bank_reconciliation_data_id) | self._get_batch_payment_aml(bank_reconciliation_data_id)
        bank_reconciliation_data_id.write({'aml_ids': [(6, 0, aml_ids.ids)]})

        # Filter by Start Date:
        if bank_reconciliation_data_id.start_date:
            hidden_transactions = aml_ids.filtered(lambda x: x.date < bank_reconciliation_data_id.start_date)
            hidden_transactions.write({'temporary_reconciled': False})
            aml_ids = aml_ids - hidden_transactions

        for line in aml_ids:
            check_number = line.payment_id.check_number if line.payment_id and line.payment_id.check_number else ''
            columns = [self._format_date(line.date),
                       line.partner_id.name if line.partner_id else '',
                       line.name,
                       check_number,
                       self.format_value(line.credit) if line.credit > 0 else '',
                       self.format_value(line.debit) if line.debit > 0 else '',
                       {'name': False, 'blocked': line.temporary_reconciled,
                        'debit': line.debit,
                        'credit': line.credit}]

            caret_type = 'account.move'
            if line.payment_id:
                caret_type = 'account.payment'
            elif line.move_id:
                if line.move_id.type in ('in_refund', 'in_invoice', 'in_receipt'):
                    caret_type = 'account.invoice.in'
                elif line.move_id.type in ('out_refund', 'out_invoice', 'out_receipt'):
                    caret_type = 'account.invoice.out'
            lines.append({
                'id': line.id,
                'name': line.move_id.name,
                'caret_options': caret_type,
                'model': 'account.move.line',
                'columns': [type(v) == dict and v or {'name': v} for v in columns],
                'level': 1,
            })

        if not lines:
            lines.append({
                'id': 'base',
                'model': 'base',
                'level': 0,
                'class': 'o_account_reports_domain_total',
                'columns': [{'name': v} for v in ['', '', '', '', '', '', '']],
            })
        return lines

    @api.model
    def _get_report_name(self):
        bank_reconciliation_data_id = self._get_bank_reconciliation_data_id()

        return bank_reconciliation_data_id.journal_id.name

    def _get_reports_buttons(self):
        return []

    def get_html(self, options, line_id=None, additional_context=None):
        bank_reconciliation_data_id = self._get_bank_reconciliation_data_id()

        if additional_context == None:
            additional_context = {}

        beginning_balance = bank_reconciliation_data_id.beginning_balance
        ending_balance = bank_reconciliation_data_id.ending_balance

        additional_context.update({
            'today': self._format_date(bank_reconciliation_data_id.statement_ending_date),
            'beginning_balance': beginning_balance,
            'ending_balance': ending_balance,
            'formatted_beginning': self.format_value(beginning_balance),
            'formatted_ending': self.format_value(ending_balance),
            'bank_reconciliation_data_id': bank_reconciliation_data_id.id
        })

        options['currency_id'] = bank_reconciliation_data_id.currency_id.id
        options['multi_company'] = None

        return super(USABankReconciliation, self).get_html(options, line_id=line_id,
                                                           additional_context=additional_context)

    def _format_date(self, date):
        return datetime.strftime(date, '%m/%d/%Y')

    def _get_bank_reconciliation_data_id(self):
        bank_reconciliation_data_id = None
        bank_id = self.env.context.get('bank_reconciliation_data_id', False)

        params = self.env.context.get('params', False)

        if not bank_id and params and params.get('action', False):
            action_obj = self.env['ir.actions.client'].browse(params['action'])
            bank_id = action_obj.params.get('bank_reconciliation_data_id', False)

        if bank_id:
            bank_reconciliation_data_id = self.env['account.bank.reconciliation.data'].browse(bank_id)

        if not bank_reconciliation_data_id:
            raise UserError(_('Cannot get Bank\'s information.'))

        if bank_reconciliation_data_id.state == 'reconciled':
            raise UserError(_('You can not access this screen anymore because it is already reconciled.'))

        return bank_reconciliation_data_id

    def open_batch_deposit_document(self, options, params=None):
        if not params:
            params = {}
        ctx = self.env.context.copy()
        ctx.pop('id', '')
        batch_id = params.get('id')
        if batch_id:
            view_id = self.env['ir.model.data'].get_object_reference('account_batch_payment', 'view_batch_payment_form')[1]
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'tree',
                'view_mode': 'form',
                'views': [(view_id, 'form')],
                'res_model': 'account.batch.payment',
                'view_id': view_id,
                'res_id': batch_id,
                'context': ctx,
            }
