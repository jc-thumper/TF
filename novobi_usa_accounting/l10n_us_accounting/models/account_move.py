# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_is_zero
from datetime import date
from dateutil import relativedelta
from itertools import zip_longest
from collections import deque
import operator as py_operator
import json
import locale
import logging

_logger = logging.getLogger(__name__)


OPERATORS = {'<': py_operator.lt, '>': py_operator.gt, '<=': py_operator.le, '>=': py_operator.ge, '=': py_operator.eq,
             '!=': py_operator.ne}


class AccountMoveUSA(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'mail.thread', 'mail.activity.mixin']

    # Override
    state = fields.Selection(track_visibility='onchange')

    # New fields
    has_been_reviewed = fields.Boolean(string='Have been reviewed?', compute='_compute_has_been_reviewed')
    ar_in_charge = fields.Many2one(string='AR In Charge', comodel_name='res.users')
    aging_days = fields.Integer(string='Aging Days', compute='_compute_aging_days', search='_search_aging_days',
                                store=True)
    fiscal_quarter = fields.Char(string='Fiscal Quarter', compute='_compute_fiscal_quarter',
                                 search='_search_fiscal_quarter')
    last_fiscal_quarter = fields.Char(string='Last Fiscal Quarter', compute='_compute_last_fiscal_quarter',
                                      search='_search_last_fiscal_quarter')
    fiscal_year = fields.Date(string='Fiscal Year', compute='_compute_fiscal_year', search='_search_fiscal_year')
    last_fiscal_year = fields.Date(string='Last Fiscal Year', compute='_compute_last_fiscal_year',
                                   search='_search_last_fiscal_year')
    is_write_off = fields.Boolean(string='Is Write Off', default=False)

    # Onchange
    @api.onchange('partner_id')
    def _onchange_select_customer(self):
        self.ar_in_charge = self.partner_id.ar_in_charge

    # Compute/Inverse/Search
    def _compute_has_been_reviewed(self):
        for record in self:
            statement_ids = record.line_ids.mapped('statement_line_id')
            record.has_been_reviewed = True if statement_ids else False

    def _compute_fiscal_quarter(self):
        for record in self:
            record.fiscal_quarter = None

    def _compute_last_fiscal_quarter(self):
        for record in self:
            record.last_fiscal_quarter = None

    def _compute_fiscal_year(self):
        for record in self:
            record.fiscal_year = None

    def _compute_last_fiscal_year(self):
        for record in self:
            record.last_fiscal_year = None

    def _search_fiscal_year(self, operator, value):
        fiscal_year_date = self._get_fiscal_year_date()

        return ['&', ('invoice_date', '>=', str(fiscal_year_date + relativedelta.relativedelta(years=-1, days=1))),
                ('invoice_date', '<=', str(fiscal_year_date))]

    def _get_fiscal_year_date(self):
        company_id = self.env.company
        last_day = str(company_id.fiscalyear_last_day)
        last_month = str(company_id.fiscalyear_last_month)
        return fields.Date.from_string('-'.join((str(date.today().year), last_month, last_day)))

    def _search_fiscal_quarter(self, operator, value):
        start_quarter = self._calculate_start_quarter()
        end_quarter = start_quarter + relativedelta.relativedelta(months=3, days=-1)

        return ['&', ('invoice_date', '>=', str(start_quarter)), ('invoice_date', '<=', str(end_quarter))]

    def _calculate_start_quarter(self):
        fiscal_year_date = self._get_fiscal_year_date()

        months = deque(range(1, 13))
        months.rotate(12 - fiscal_year_date.month)
        new_months = list(months)

        current_month = date.today().month

        quarter = None
        is_decrease_year = False
        index = 0
        for month_group in zip_longest(*[iter(new_months)] * 3):
            for month in month_group:
                if current_month == month:
                    quarter = index // 3 + 1
                    if month_group[0] > month_group[-1] and current_month == month_group[-1]:
                        is_decrease_year = True
                    break
                index += 1
            if quarter:
                break

        start_month = str(new_months[::3][quarter - 1])
        start_year = str(fiscal_year_date.year - 1) if is_decrease_year else str(fiscal_year_date.year)
        return fields.Date.from_string('-'.join((start_year, start_month, '1')))

    def _search_last_fiscal_quarter(self, operator, value):
        start_quarter = self._calculate_start_quarter()
        last_quarter_start = start_quarter + relativedelta.relativedelta(months=-3)
        last_quarter_end = start_quarter + relativedelta.relativedelta(days=-1)

        return ['&', ('invoice_date', '>=', str(last_quarter_start)), ('invoice_date', '<=', str(last_quarter_end))]

    def _search_last_fiscal_year(self, operator, value):
        fiscal_year_date = self._get_fiscal_year_date()
        last_year_start = fiscal_year_date + relativedelta.relativedelta(years=-2, days=1)
        last_year_end = fiscal_year_date + relativedelta.relativedelta(years=-1)

        return ['&', ('invoice_date', '>=', str(last_year_start)), ('invoice_date', '<=', str(last_year_end))]

    # Use Odoo OOTB instead.
    # def _recompute_invoice_due_date(self):
    #     """
    #     By default, Odoo gets the last day when invoice/bill is paid completely.
    #     But if the invoice/bill has multiple due date (e.g.: payment terms is 30% immediately, the remaining at the end
    #     of following month), we should take the earliest due date (that hasn't been fulfilled) to calculate aging days
    #     of the whole invoice/bill.
    #     """
    #     today = fields.Date.context_today(self)
    #     for record in self:
    #         aml_ids = record.line_ids \
    #             .filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable') and line.amount_residual > 0) \
    #             .sorted(lambda line: line.date_maturity or today)
    #         if aml_ids:
    #             record.invoice_date_due = aml_ids[0].date_maturity
    #
    # def _compute_amount(self):
    #     # Recompute invoice_date_due after changing Amount Residual...
    #     super(AccountMoveUSA, self)._compute_amount()
    #     self._recompute_invoice_due_date()
    #
    # def _recompute_payment_terms_lines(self):
    #     # Recompute invoice_date_due after changing Payment Term,...
    #     super(AccountMoveUSA, self)._recompute_payment_terms_lines()
    #     self._recompute_invoice_due_date()

    @api.depends('invoice_date_due', 'state', 'invoice_payment_state')
    def _compute_aging_days(self):
        today = fields.Date.today()
        for record in self:
            aging_days = 0
            if record.state == 'posted' and record.invoice_payment_state == 'not_paid' and record.invoice_date_due:
                aging_days = (today - record.invoice_date_due).days
            record.aging_days = max(aging_days, 0)

    @api.model
    def _search_aging_days(self, operator, value):
        ids = [invoice.id for invoice in self.search([]) if OPERATORS[operator](invoice.aging_days, value)]
        return [('id', 'in', ids)]

    # Others
    def _compute_payments_widget_to_reconcile_info(self):
        super(AccountMoveUSA, self)._compute_payments_widget_to_reconcile_info()
        try:
            outstanding_credits_debits = json.loads(self.invoice_outstanding_credits_debits_widget)
            content = outstanding_credits_debits['content']
            content_dict = {line['id']: line for line in content}

            for line in self.env['account.move.line'].browse(content_dict.keys()):
                content_dict[line['id']].update({
                    'payment_id': line.payment_id.id,
                    'move_id': line.move_id.id,
                    'journal_name': line.move_id.name or line.ref,
                })
            outstanding_credits_debits['type'] = self.type

            self.invoice_outstanding_credits_debits_widget = json.dumps(outstanding_credits_debits)
        except Exception as _:
            pass
        return True

    def get_payment_move_line_ids(self):
        """
        account_invoice.payment_move_line_ids has been removed. This function is to retrieve it.
        :return: payment_move_line_ids
        """
        self.ensure_one()
        line_ids = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        partial_ids = line_ids.mapped('matched_debit_ids') + line_ids.mapped('matched_credit_ids')
        payment_move_line_ids = self.env['account.move.line']

        for partial in partial_ids:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id
            payment_move_line_ids |= counterpart_lines.filtered(lambda line: line not in self.line_ids)

        return payment_move_line_ids

    def _get_sequence(self):
        """
        Override from Odoo.
        Get sequence for account.move in case that it's write-off
        :return: write_off_sequence_id if is_write_off else super()
        """
        journal = self.journal_id
        if self.type in ['out_refund', 'in_refund'] and self.is_write_off:
            return journal.write_off_sequence_id
        return super(AccountMoveUSA, self)._get_sequence()

    def _log_message_move(self, values):
        if 'line_ids' in values:
            for record in self:
                msg = "<b>Journal Entry lines have been updated:</b><ul>"
                for line in record.line_ids:
                    msg += "<li>{}: {}</li>".format(line.account_id.name, line.balance)
                msg += "</ul>"
                record.message_post(body=msg, message_type="comment", subtype="mail.mt_note")

    @api.model
    def _cron_aging_days(self):
        invoices = self.search([('invoice_payment_state', '=', 'not_paid'), ('invoice_date_due', '!=', False)])
        _logger.info('===== Start updating Aging Days for {} invoices ====='.format(len(invoices)))
        invoices._compute_aging_days()
        _logger.info('===== Finish updating Aging Days for {} invoices ====='.format(len(invoices)))

    def create_refund(self, write_off_amount, company_currency_id, account_id, invoice_date=None, description=None,
                      journal_id=None):
        new_invoices = self.browse()
        for invoice in self:
            # Copy from Odoo
            reverse_type_map = {
                'entry': 'entry',
                'out_invoice': 'out_refund',
                'out_refund': 'entry',
                'in_invoice': 'in_refund',
                'in_refund': 'entry',
                'out_receipt': 'entry',
                'in_receipt': 'entry',
            }
            reconcile_account_id = invoice.partner_id.property_account_receivable_id \
                if invoice.is_sale_document(include_receipts=True) else invoice.partner_id.property_account_payable_id
            reverse_type = reverse_type_map[invoice.type]

            default_values = {
                'ref': description,
                'date': invoice_date,
                'invoice_date': invoice_date,
                'invoice_date_due': invoice_date,
                'journal_id': journal_id,
                'invoice_payment_term_id': None,
                'type': reverse_type,
                'invoice_origin': invoice.name,
                'state': 'draft'
            }
            values = invoice._reverse_move_vals(default_values, False)

            line_ids = values.pop('line_ids')
            if 'invoice_line_ids' in values:
                values.pop('invoice_line_ids')
            new_invoice_line_ids = self._build_invoice_line_item(abs(write_off_amount), account_id.id, line_ids, reconcile_account_id, reverse_type)

            # Update value from Write Off An Account form
            # Update is_write_off flag
            if invoice.type == 'out_invoice':
                values['is_write_off'] = True
            values['fiscal_position_id'] = False

            refund_invoice = self.create(values)
            refund_invoice.write({'invoice_line_ids': new_invoice_line_ids})

            # Create message post
            message = 'This write off was created from ' \
                      '<a href=# data-oe-model=account.move data-oe-id={}>{}</a>'.format(invoice.id, invoice.name)
            refund_invoice.message_post(body=message)

            new_invoices += refund_invoice
        return new_invoices

    @staticmethod
    def _build_invoice_line_item(write_off_amount, account_id, line_ids, reconcile_account_id, reverse_type):
        new_invoice_line_ids = {}
        if line_ids:
            debit_wo, credit_wo = (0, write_off_amount) if reverse_type == 'in_refund' else (write_off_amount, 0)
            # We write in invoice_line_ids, so all values must be positive
            # if reverse_type == 'in_refund':
            #     write_off_amount *= -1

            new_invoice_line_ids = {
                'name': 'Write Off',
                'display_name': 'Write Off',
                'product_uom_id': False,
                'account_id': account_id,
                'quantity': 1.0,
                'price_unit': write_off_amount,
                'product_id': False,
                'discount': 0.0,
                'debit': debit_wo,
                'credit': credit_wo
            }
        return [(0, 0, new_invoice_line_ids)]

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        for index, item in reversed(list(enumerate(domain or []))):
            if 'amount_total_signed' in item and type(item[2]) == str:
                amount = item[2]
                locale.setlocale(locale.LC_ALL, '{}.UTF-8'.format(self.env.lang))
                try:
                    item[2] = locale.atof(amount.replace(self.env.company.currency_id.symbol, ''))
                except ValueError:
                    # Remove data and operator
                    del domain[index]
                    domain.remove('|')
                break
        return super(AccountMoveUSA, self).search_read(domain, fields, offset, limit, order)

    def action_delete(self):
        self.unlink()
        return {'type': 'ir.actions.client', 'tag': 'history_back'}

    def button_draft(self):
        aml_ids = self.mapped('line_ids')
        # Undo reconciled on each journal items
        aml_ids.write({'bank_reconciled': False})

        # Trigger function to update Changes in reconciliation report.
        reconciliation_line_ids = self.env['account.bank.reconciliation.data.line'].search(
            [('aml_id', 'in', aml_ids.ids)])
        reconciliation_line_ids.compute_change_status()

        super(AccountMoveUSA, self).button_draft()

    def button_draft_usa(self):
        self.ensure_one()
        action = self.env.ref('l10n_us_accounting.action_view_button_set_to_draft_message').read()[0]
        action['context'] = isinstance(action.get('context', {}), dict) or {}
        action['context']['default_move_id'] = self.id
        return action

    def open_form(self):
        # TODO: wrong action here
        self.ensure_one()
        action = False
        if self.is_write_off:
            action = self.env.ref('l10n_us_accounting.action_invoice_write_off_usa').read()[0]
            action['views'] = [(self.env.ref('l10n_us_accounting.write_off_form_usa').id, 'form')]
        else:
            if self.type == 'out_refund':
                action = self.env.ref('account.action_move_out_refund_type').read()[0]
                action['views'] = [(self.env.ref('l10n_us_accounting.credit_note_form_usa').id, 'form')]
            elif self.type == 'in_refund':
                action = self.env.ref('account.action_move_in_refund_type').read()[0]
                action['views'] = [(self.env.ref('l10n_us_accounting.credit_note_supplier_form_usa').id, 'form')]
            elif self.type == 'out_invoice':
                action = self.env.ref('account.action_move_out_invoice_type').read()[0]
                action['views'] = [(self.env.ref('l10n_us_accounting.invoice_form_usa').id, 'form')]
            elif self.type == 'in_invoice':
                action = self.env.ref('account.action_move_in_invoice_type').read()[0]
                action['views'] = [(self.env.ref('l10n_us_accounting.invoice_supplier_form_usa').id, 'form')]
        return action

    def name_get(self):
        TYPES = {
            'out_invoice': 'Invoice',
            'in_invoice': 'Vendor Bill',
            'out_refund': 'Credit Note',
            'in_refund': 'Vendor Credit note',
            'write_off': 'Write-off',
        }
        result = []
        append_result = result.append
        for inv in self:
            type = 'write_off' if inv.is_write_off else inv.type
            append_result((inv.id, '{} {}'.format(inv.name or TYPES[type], inv.ref or '')))
        return result

    def _get_printed_report_name(self):
        self.ensure_one()

        if self.type == 'out_refund' and self.is_write_off:
            return self.state == 'draft' and _('Writeoff') or \
                   self.state in ('open', 'paid') and _('Writeoff - {}'.format(self.number))
        else:
            return super(AccountMoveUSA, self)._get_printed_report_name()

    def _get_reconciled_info_JSON_values(self):
        # Override Odoo's. Add partial_id, type and is_write_off to JSON values.
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(
            lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id
            counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)

            if foreign_currency and partial.currency_id == foreign_currency:
                amount = partial.amount_currency
            else:
                amount = partial.company_currency_id._convert(partial.amount, self.currency_id, self.company_id,
                                                              self.date)

            if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                continue

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'

            reconciled_vals.append({
                # ============= Add here
                'type': self.type,
                'is_write_off': counterpart_line.move_id.is_write_off,
                'partial_id': partial.id,
                # =============
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': amount,
                'currency': self.currency_id.symbol,
                'digits': [69, self.currency_id.decimal_places],
                'position': self.currency_id.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'move_type': counterpart_line.move_id.type,
                'ref': ref,
            })
        return reconciled_vals

    # CRUD
    def write(self, values):
        res = super().write(values)
        self._log_message_move(values)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # TODO: do we need to update write_off value here?
        # field_name = 'is_write_off'
        # values[field_name] = self.env.context.get(field_name, False)
        res = super().create(vals_list)
        res._log_message_move(vals_list)

        # Update AR in charge
        for record in res:
            if not record.ar_in_charge and record.partner_id.ar_in_charge:
                record.ar_in_charge = record.partner_id.ar_in_charge
        return res


class AccountMoveLineUSA(models.Model):
    _inherit = 'account.move.line'

    # Technical fields
    temporary_reconciled = fields.Boolean(default=False, copy=False)
    bank_reconciled = fields.Boolean(string='Have been reconciled?', default=False, copy=False)
    should_be_reconciled = fields.Boolean(compute='_compute_should_be_reconciled', store=True, copy=False,
                                          help='Check if this account_move_line should be in reconciliation screen.')
    is_fund_line = fields.Boolean()
    eligible_for_1099 = fields.Boolean(string='Eligible for 1099?', default=True)

    @api.depends('journal_id.default_credit_account_id', 'journal_id.default_debit_account_id', 'account_id')
    def _compute_should_be_reconciled(self):
        for record in self:
            accounts = [record.journal_id.default_credit_account_id, record.journal_id.default_debit_account_id]
            record.should_be_reconciled = record.account_id in accounts

    def update_temporary_reconciled(self, ids, checked):
        # Click on checkbox or select/deselect all on Reconciliation Screen.
        return self.browse(ids).write({'temporary_reconciled': checked})

    def mark_bank_reconciled(self):
        """
        Apply reconcile on Reconciliation Screen.
        - Set bank_reconciled = True for this account_move_line.
        - Check payment. If all Bank lines in this payment have been reconciled, mark it reconciled.
        - Check BSL. If all Journal Items in this BSL have been reconciled, mark it reconciled.
        """
        self.write({'bank_reconciled': True})

        for payment in self.mapped('payment_id'):
            if False not in payment.move_line_ids.filtered('should_be_reconciled').mapped('bank_reconciled'):
                payment.state = 'reconciled'

        for statement in self.mapped('statement_line_id'):
            if False not in statement.journal_entry_ids.filtered('should_be_reconciled').mapped('bank_reconciled'):
                statement.status = 'reconciled'

        self.mapped('statement_line_id')\
            .filtered(lambda r: False not in r.journal_entry_ids.mapped('bank_reconciled'))\
            .write({'status': 'reconciled'})

    def undo_bank_reconciled(self):
        """
        Undo last reconciliation.
        - Set bank_reconciled = False for this account_move_line.
        - Set state of its payment to 'posted'.
        - Set status of BSL to 'confirm'.
        """
        self.write({'bank_reconciled': False})

        self.mapped('payment_id').write({'state': 'posted'})

        self.mapped('statement_line_id')\
            .filtered(lambda x: x.status == 'reconciled')\
            .write({'status': 'confirm'})

    # get partial reconcile moves to unlink
    def _get_rec_move_ids(self, part_rec_ids, invoice_id):
        rec_move_ids = self.env['account.partial.reconcile']
        aml_to_keep = (invoice_id.line_ids | invoice_id.line_ids.mapped('full_reconcile_id.exchange_move_id.line_ids')).ids

        for rec in part_rec_ids:
            if rec.debit_move_id.id in aml_to_keep or rec.credit_move_id.id in aml_to_keep:
                rec_move_ids += rec

        return rec_move_ids

    def remove_move_reconcile(self):
        """
        Handle 3 basic cases:
        1. Set to draft 1 payment.
            - Remove all links between this payment and other transactions (super())
            - Delete all usa_payment_invoice lines inside this payment.
        2. Set to draft invoice/bill/...:
            - Remove all links between this invoice/bill and other payments that paid for it. (super())
            - Delete all usa_payment_invoice lines that paid for this invoice/bill
        3. Use Odoo's widget to remove 1 partial:
            - Update usa_payment_invoice line (decrease amount or remove line) that paid for it.
            - Delete this partial.
        """
        context = self.env.context
        partial_id = context.get('partial_id', False)
        if not partial_id:
            payments = context.get('from_payment', False)
            # Set to draft payment, remove all applied invoice in this payment.
            if payments:
                payments = self.env['account.payment'].browse(payments)
                payments.mapped('open_invoice_ids').unlink()
            else:
                move_ids = self.mapped('move_id')
                self.env['usa.payment.invoice'].search([('invoice_id', 'in', move_ids.ids)]).unlink()
            super(AccountMoveLineUSA, self).remove_move_reconcile()
        else:
            # Remove one partial payment on invoice/bill form
            partial_id = self.env['account.partial.reconcile'].browse([partial_id])
            move_line_id = partial_id.debit_move_id + partial_id.credit_move_id
            payment_id = move_line_id.mapped('payment_id')  # Expect 1 record.
            usa_payment_invoice_id = payment_id.open_invoice_ids.filtered(lambda r: r.account_move_line_id in move_line_id)
            amount_remove = partial_id.amount
            # On invoice/bill form, we could add multiple partials using same payment. So when removing 1 partial,
            # need to check to decide that we should remove the usa_payment_invoice line, or just decrease its amount.
            if usa_payment_invoice_id.payment > amount_remove:
                usa_payment_invoice_id.payment -= amount_remove
            else:
                usa_payment_invoice_id.unlink()

            partial_id.unlink()

    def _reconcile_lines(self, debit_moves, credit_moves, field):
        """ This function loops on the 2 recordsets given as parameter as long as it
            can find a debit and a credit to reconcile together. It returns the recordset of the
            account move lines that were not reconciled during the process.
        """
        (debit_moves + credit_moves).read([field])
        to_create = []
        cash_basis = debit_moves and debit_moves[0].account_id.internal_type in ('receivable', 'payable') or False
        cash_basis_percentage_before_rec = {}

        # get partial amount
        partial_total = self.env.context.get('partial_amount', False)
        is_partial = True if partial_total else False

        while debit_moves and credit_moves:
            debit_move = debit_moves[0]
            credit_move = credit_moves[0]
            company_currency = debit_move.company_id.currency_id
            # We need those temporary value otherwise the computation might be wrong below
            temp_amount_residual = min(debit_move.amount_residual, -credit_move.amount_residual)
            temp_amount_residual_currency = min(debit_move.amount_residual_currency, -credit_move.amount_residual_currency)
            amount_reconcile = min(debit_move[field], -credit_move[field])

            # # TODO: Support multi currencies
            if is_partial:
                if float_is_zero(partial_total, precision_digits=2):
                    break

                amount_reconcile = min(amount_reconcile, partial_total)
                partial_total -= amount_reconcile

                if not debit_move.currency_id and not credit_move.currency_id:  # expressed in company currency
                    temp_amount_residual = amount_reconcile
                    temp_amount_residual_currency = 0
                # elif debit_move.currency_id and debit_move.currency_id == credit_move.currency_id:
                #     temp_amount_residual = self._convert_amount(debit_move.currency_id, company_currency, amount_reconcile)
                #     temp_amount_residual_currency = amount_reconcile

            # Remove from recordset the one(s) that will be totally reconciled
            # For optimization purpose, the creation of the partial_reconcile are done at the end,
            # therefore during the process of reconciling several move lines, there are actually no recompute performed by the orm
            # and thus the amount_residual are not recomputed, hence we have to do it manually.
            if amount_reconcile == debit_move[field]:
                debit_moves -= debit_move
            else:
                debit_moves[0].amount_residual -= temp_amount_residual
                debit_moves[0].amount_residual_currency -= temp_amount_residual_currency

            if amount_reconcile == -credit_move[field]:
                credit_moves -= credit_move
            else:
                credit_moves[0].amount_residual += temp_amount_residual
                credit_moves[0].amount_residual_currency += temp_amount_residual_currency
            # Check for the currency and amount_currency we can set
            currency = False
            amount_reconcile_currency = 0
            if field == 'amount_residual_currency':
                currency = credit_move.currency_id.id
                amount_reconcile_currency = temp_amount_residual_currency
                amount_reconcile = temp_amount_residual

            if cash_basis:
                tmp_set = debit_move | credit_move
                cash_basis_percentage_before_rec.update(tmp_set._get_matched_percentage())

            to_create.append({
                'debit_move_id': debit_move.id,
                'credit_move_id': credit_move.id,
                'amount': amount_reconcile,
                'amount_currency': amount_reconcile_currency,
                'currency_id': currency,
            })

            # if self.env.context.get('partial_amount', False):
            #     break

        part_rec = self.env['account.partial.reconcile']
        index = 0
        with self.env.norecompute():
            for partial_rec_dict in to_create:
                new_rec = self.env['account.partial.reconcile'].create(partial_rec_dict)
                part_rec += new_rec
                if cash_basis:
                    new_rec.create_tax_cash_basis_entry(cash_basis_percentage_before_rec)
                    index += 1
        self.recompute()

        return debit_moves+credit_moves

    def reconcile(self, writeoff_acc_id=False, writeoff_journal_id=False):
        """
        This function is to add applied journal items to payment.

        CUSTOMER PAYMENT:
        Payment is credit move.
        Invoices and opening balance are debit move.
        """
        debit_moves = self.filtered(lambda r: r.debit != 0 or r.amount_currency > 0)
        credit_moves = self.filtered(lambda r: r.credit != 0 or r.amount_currency < 0)
        debit_moves = debit_moves.sorted(key=lambda a: (a.date_maturity or a.date, a.currency_id))
        credit_moves = credit_moves.sorted(key=lambda a: (a.date_maturity or a.date, a.currency_id))

        res = super(AccountMoveLineUSA, self).reconcile(writeoff_acc_id, writeoff_journal_id)

        # Customer Payment
        if not credit_moves or not debit_moves:
            return res

        internal_type = 'receivable'
        invoice_amls = []
        payment_move = False
        if credit_moves and credit_moves[0].account_id.internal_type == 'receivable':
            payment_move = credit_moves[0]
            invoice_amls = debit_moves
        elif debit_moves and debit_moves[0].account_id.internal_type == 'payable':
            payment_move = debit_moves[0]
            invoice_amls = credit_moves
            internal_type = 'payable'

        if not payment_move or not invoice_amls:
            return res

        if payment_move.payment_id:
            payment = payment_move.payment_id
            for invoice_aml in invoice_amls:
                total_amount = self._get_payment_amount(invoice_aml, payment_move, internal_type)

                if not total_amount:
                    continue

                existing_ids = [line.account_move_line_id.id for line in payment.open_invoice_ids]
                if invoice_aml.id not in existing_ids:
                    payment.with_context(usa_reconcile=True).write(
                        {'open_invoice_ids': [(0, 0, {'account_move_line_id': invoice_aml.id,
                                                      'payment': total_amount})]})
                else:
                    update_line = payment.open_invoice_ids.filtered(lambda x: x.account_move_line_id == invoice_aml)
                    payment.with_context(usa_reconcile=True).write(
                        {'open_invoice_ids': [(1, update_line.id, {'payment': total_amount})]})

        return res

    def _get_payment_amount(self, invoice_aml, payment_move, internal_type):
        if not internal_type:
            return False

        payment = payment_move.payment_id
        match_field = 'matched_credit_ids'
        side_field = 'credit_move_id'
        if internal_type == 'payable':
            match_field = 'matched_debit_ids'
            side_field = 'debit_move_id'

        to_currency = payment.currency_id
        return sum([self._convert_amount(False, to_currency, p.amount, p)
                    for p in invoice_aml[match_field] if p[side_field] in payment.move_line_ids])

    def _convert_amount(self, from_currency, to_currency, amount, partial_reconcile=None):
        if partial_reconcile and partial_reconcile.currency_id == to_currency:
            return partial_reconcile.amount_currency

        company_id = self.env.company
        from_currency = from_currency or company_id.currency_id
        if from_currency != to_currency:
            return from_currency._convert(amount, to_currency, company_id, fields.Date.today())
        return amount

    def unlink(self):
        statement_ids = self.mapped('statement_line_id')
        super(AccountMoveLineUSA, self).unlink()

        # If all journal items of a BSL is removed, set status to draft
        statement_ids.filtered(lambda r: not r.journal_entry_ids).write({'status': 'open'})
