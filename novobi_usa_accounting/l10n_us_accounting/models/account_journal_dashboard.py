# -*- coding: utf-8 -*-

import ast
import logging
import time

from odoo import api, fields, models, _
from odoo.tools import safe_eval, formatLang

from ..models.model_const import (
    ACCOUNT_RECONCILE_MODEL,
    ACCOUNT_BANK_STATEMENT_LINE,
    ACCOUNT_MOVE_LINE,
    ACCOUNT_BATCH_DEPOSIT,
    ACCOUNT_BANK_RECONCILIATION_DATA,
    ACCOUNT_PAYMENT,
)
from ..utils import action_utils
from ..utils import bank_statement_line_utils

_logger = logging.getLogger(__name__)


class AccountJournalUSA(models.Model):
    _inherit = 'account.journal'

    def get_journal_dashboard_datas(self):
        data = super(AccountJournalUSA, self).get_journal_dashboard_datas()
        if self.type in ['bank', 'cash']:
            previous_reconciliation = self.env[ACCOUNT_BANK_RECONCILIATION_DATA].search(
                [('journal_id', '=', self.id), ('state', '=', 'reconciled')], order='id desc', limit=1)
            ending_balance = previous_reconciliation and previous_reconciliation.ending_balance or 0.0
            currency = self.currency_id or self.company_id.currency_id
            new_last_balance = formatLang(self.env, currency.round(ending_balance), currency_obj=currency)

            data.update({
                'number_for_reviews': self.env[ACCOUNT_BANK_STATEMENT_LINE].search_count([
                    ('journal_id', '=', self.id), ('status', '=', 'open')
                ]),
                'new_last_balance': new_last_balance,
            })
        else:
            data.update({
                'number_for_reviews': 0,
                'new_last_balance': 0,
            })
        return data

    def open_action_reconciliation(self):
        get_context_env = self.env.context.get
        action_name = get_context_env('action_name')
        if not action_name:
            return False

        ctx = self._context.copy()
        ctx.pop('group_by', None)
        ir_model_obj = self.env['ir.model.data']
        model, action_id = ir_model_obj.get_object_reference('l10n_us_accounting', action_name)
        [action] = self.env[model].browse(action_id).read()

        domain = ast.literal_eval(action['domain'])
        domain.append(('journal_id', '=', self.id))

        action.update({
            'context': ctx,
            'display_name': ' '.join((action['name'], 'from', self.name)),
            'domain': domain,
        })

        return action

    def action_usa_reconcile(self):
        """
        Either open a popup to set Ending Balance & Ending date
        or go straight to Reconciliation Screen
        """
        draft_reconciliation = self.env['account.bank.reconciliation.data']. \
            search([('journal_id', '=', self.id), ('state', '=', 'draft')], limit=1)

        # If a draft reconciliation is found, go to that screen
        if draft_reconciliation:
            return draft_reconciliation.open_reconcile_screen()

        # open popup
        action = self.env.ref('l10n_us_accounting.action_bank_reconciliation_data_popup').read()[0]
        action['context'] = {'default_journal_id': self.id}
        return action

    def open_action(self):
        self.ensure_one()
        """return action based on type for related journals"""
        action = super(AccountJournalUSA, self).open_action()
        search_view_id = self._context.get('search_view_id', False)
        if search_view_id:
            account_invoice_filter = self.env.ref(search_view_id, False)
            if account_invoice_filter:
                action['search_view_id'] = (account_invoice_filter.id, account_invoice_filter.name)

        return action

    def action_create_new_credit_note(self):
        """ This is a new method, call action_create_new method from super
            Because action returned from action_create_new method use view_id for invoice and bill only,
            so we change the view_id to open the correct credit note form
        """
        action = super(AccountJournalUSA, self).action_create_new()
        # TODO: now they're using the same form in Odoo 13
        if action['view_id'] == self.env.ref('account.view_move_form').id:
            action['view_id'] = self.env.ref('l10n_us_accounting.credit_note_form_usa').id
        # elif action['view_id'] == self.env.ref('account.view_move_form').id:
        #     action['view_id'] = self.env.ref('l10n_us_accounting.credit_note_supplier_form_usa').id
        return action

    def open_payments_action(self, payment_type, mode=False):
        action = super(AccountJournalUSA, self).open_payments_action(payment_type, mode)
        if action:
            display_name = self.env.context.get('display_name', False)
            if display_name:
                action['display_name'] = display_name

            if payment_type == 'inbound':
                action_utils.update_views(action, 'tree', self.env.ref('account.view_account_payment_tree').id)
            elif payment_type == 'outbound':
                action_utils.update_views(action, 'tree', self.env.ref('account.view_account_supplier_payment_tree').id)
            elif payment_type == 'transfer':
                action_utils.update_views(action, 'tree',
                                          self.env.ref('l10n_us_accounting.view_account_internal_transfer_tree_usa').id)

            return action

    def open_bank_statement_line(self):
        domain = [('journal_id', 'in', self.ids)] if self else []
        context = dict(self._context or {})
        context.update(create=False, edit=False)

        status = context.get('status', False)
        if status:
            domain.append(('status', '=', status))

        names = {
            'excluded':     _('Excluded Items'),
            'confirm':      _('Reviewed Items'),
            'reconciled':   _('Reconciled Items')
        }

        return {
            'name': names.get(status, _('Bank Statement Lines')),
            'res_model': 'account.bank.statement.line',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'search_view_id': self.env.ref('l10n_us_accounting.view_bank_statement_line_search_usa').id,
            'domain': domain,
            'target': 'current',
            'context': context
        }
