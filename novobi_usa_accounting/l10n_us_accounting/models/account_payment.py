# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero
from odoo.tools.misc import formatLang
from ..utils.utils import has_multi_currency_group


class AccountPaymentUSA(models.Model):
    _inherit = 'account.payment'

    # set "required=False" and modify required condition in view
    journal_id = fields.Many2one(domain=[('type', 'in', ('bank', 'cash'))], string='Bank Account', required=False)
    ar_in_charge = fields.Many2one(string='AR In Charge', comodel_name='res.users')

    # Add Open invoices to Payment
    open_invoice_ids = fields.One2many('usa.payment.invoice', 'payment_id')
    has_open_invoice = fields.Boolean(compute='_get_has_open_invoice', store=True)
    available_move_line_ids = fields.Many2many('account.move.line', compute='_get_available_move_line', store=True)

    payment_with_invoices = fields.Monetary('Payment with Invoices', compute='_compute_payment_with_invoices', store=True)
    outstanding_payment = fields.Monetary('Outstanding Payment', compute='_compute_outstanding_payment', store=True)
    writeoff_amount = fields.Monetary('Write-off Amount', compute='_compute_writeoff_amount', store=True)

    # Technical fields
    check_number_text = fields.Char(compute='_compute_check_number_text', store=True)
    display_applied_invoices = fields.Boolean(compute='_get_display_applied_invoices',
                                              help="Technical field to display/hide applied invoices")
    has_been_reviewed = fields.Boolean(string='Have been reviewed?', compute='_compute_has_been_reviewed',
                                       store=True, default=False, copy=False)
    has_been_voided = fields.Boolean('Voided?', copy=False)

    # Record check
    is_payment_receipt = fields.Boolean(string='Is Payment Receipt?', default=False)
    expense_account = fields.Many2one('account.account', string='Expense Account',
                                      domain=lambda self: [('user_type_id', 'in', [self.env.ref('account.data_account_type_expenses').id,
                                                                                   self.env.ref('account.data_account_type_direct_costs').id])])
    income_account = fields.Many2one('account.account', string='Income Account',
                                     domain=lambda self: [('user_type_id', 'in', [self.env.ref('account.data_account_type_revenue').id,
                                                                                  self.env.ref('account.data_account_type_other_income').id])])

    @api.depends('move_line_ids', 'move_line_ids.statement_line_id', 'journal_id')
    def _compute_has_been_reviewed(self):
        for record in self:
            accounts = [record.journal_id.default_debit_account_id, record.journal_id.default_credit_account_id]
            aml_ids = record.move_line_ids.filtered(lambda r: r.account_id in accounts)
            record.has_been_reviewed = True if aml_ids and not aml_ids.filtered(lambda r: not r.statement_line_id) else False

    # Keep Invoice/Bill Open or Write-off
    payment_writeoff_option = fields.Selection([
        ('open', 'Keep open'), ('reconcile', 'Mark invoice as fully paid')],
        default='open', string="Payment Write-off Option", copy=False)

    @api.constrains('amount', 'payment_with_invoices', 'payment_type')
    def _check_amount_and_payment_with_invoices(self):
        for record in self:
            if record.outstanding_payment < 0:
                raise ValidationError(_('Outstanding Payment cannot be negative.'))

    @api.depends('open_invoice_ids', 'open_invoice_ids.payment')
    def _compute_payment_with_invoices(self):
        """
        Compute Payment with Invoices/Bills.
        Payment with Invoices/Bills = Total payment of all applied invoices/bills.
        """
        for record in self:
            record.payment_with_invoices = sum(inv.payment for inv in record.open_invoice_ids) if record.open_invoice_ids else 0

    @api.depends('move_line_ids', 'destination_account_id', 'journal_id.default_debit_account_id', 'journal_id.default_credit_account_id')
    def _compute_writeoff_amount(self):
        """
        Compute writeoff amount for this payment.
        - Total amount = Total balance of all lines having account in [default_debit_account_id, default_credit_account_id]
        of bank account. Use this instead of Amount of payment to not depend on it.

        - Counterpart amount = Total balance of all lines having account same to Destination Account.
            Ex:     - Customer payment: Account Receivable
                    - Vendor payment: Account Payable
                    - Customer Deposit: Customer Deposit

        WRITEOFF AMOUNT = Total amount - Counterpart amount
        """
        for record in self:
            if record.state in ['draft', 'cancelled']:
                writeoff_amount = 0
            else:
                company_currency = record.company_id.currency_id
                accounts = [record.journal_id.default_debit_account_id, record.journal_id.default_credit_account_id]
                amount = sum(record.move_line_ids.filtered(lambda r: r.account_id in accounts).mapped('balance'))
                counterpart_amount = sum(record.move_line_ids.filtered(lambda r: r.account_id == record.destination_account_id).mapped('balance'))
                writeoff_amount = abs(amount) - abs(counterpart_amount)

                if record.currency_id != company_currency:
                    writeoff_amount = record.currency_id._convert(writeoff_amount, company_currency, record.company_id, record.payment_date)

            record.writeoff_amount = writeoff_amount

    @api.depends('payment_with_invoices', 'writeoff_amount', 'amount', 'state')
    def _compute_outstanding_payment(self):
        """
        Compute Outstanding payment.
        - Update Amount: when users apply Open Invoice/Bill, Amount is calculate automatically and Outstanding is 0.
        - Outstanding payment = Total Amount - (Payment with Invoices/Bills + Write-off Amount)
        """
        for record in self:
            if record.state == 'draft' and float_is_zero(record.outstanding_payment, precision_digits=2) and record.open_invoice_ids and not record.writeoff_amount:
                record.amount = record.payment_with_invoices

            record.outstanding_payment = record.amount - (record.payment_with_invoices + record.writeoff_amount)

    # not return super()
    @api.onchange('amount', 'currency_id')
    def _onchange_amount(self):
        super(AccountPaymentUSA, self)._onchange_amount()
        # Change amount of payment manually.
        self.outstanding_payment = self.amount - (self.writeoff_amount + self.payment_with_invoices)
        return self.get_bank_account()

    @api.depends('check_number')
    def _compute_check_number_text(self):
        for record in self:
            record.check_number_text = record.check_number and str(record.check_number)

    @api.depends('open_invoice_ids', 'has_open_invoice', 'payment_type', 'partner_type', 'writeoff_amount')
    def _get_display_applied_invoices(self):
        register_payment_context = True if self.env.context.get('active_model') == 'account.move' else False

        for record in self:
            if not float_is_zero(record.writeoff_amount, precision_rounding=2):
                record.display_applied_invoices = True
            elif (record.open_invoice_ids or record.has_open_invoice) and not register_payment_context and \
                    ((record.payment_type == 'inbound' and record.partner_type == 'customer') or
                     (record.payment_type == 'outbound' and record.partner_type == 'supplier')):
                record.display_applied_invoices = True
            else:
                record.display_applied_invoices = False

    @api.onchange('partner_id')
    def _onchange_select_customer(self):
        self.ar_in_charge = self.partner_id.ar_in_charge

    def get_bank_account(self):
        domain = {}
        journal_domain = [('type', 'in', ('bank', 'cash'))]

        if self.payment_type in ['inbound', 'outbound']:
            methods_field = self.payment_type + '_payment_method_ids'
            if self.payment_method_id:
                journal_domain.append((methods_field + '.id', '=', self.payment_method_id.id))

            if self.journal_id:
                domain['payment_method_id'] = [('id', 'in', self.journal_id[methods_field].ids)]

        domain['journal_id'] = journal_domain
        return {'domain': domain}

    def button_journal_entries(self):
        action = super(AccountPaymentUSA, self).button_journal_entries()
        action['name'] = _('Journal Entry')
        return action

    def post(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_('Payment Amount must be greater than 0'))

        self._create_write_off()

        res = super(AccountPaymentUSA, self).post()

        # reconcile payment with open invoices
        for payment in self:
            # move_line is one of the aml of the current payment
            move_line = payment.move_line_ids.filtered(lambda line: line.account_id == payment.destination_account_id)

            if len(move_line) == 1:  # in case of internal transfer to the same account
                if move_line.reconciled is False:  # register payment in Invoice form
                    ctx = {}
                    for open_invoice in payment.open_invoice_ids.sorted(key=lambda r: r.id):
                        if not has_multi_currency_group(self):
                            ctx = {'partial_amount': open_invoice.payment}

                        if open_invoice.invoice_id:  # for invoice
                            invoice_id = open_invoice.invoice_id
                            invoice_id.with_context(ctx).js_assign_outstanding_line(move_line.id)
                        else:  # for journal entry
                            mv_line_ids = [move_line.id, open_invoice.account_move_line_id.id]
                            self.env['account.reconciliation.widget'].with_context(ctx)\
                                .process_move_lines([{'mv_line_ids': mv_line_ids, 'type': 'account',
                                                      'id': payment.destination_account_id.id,
                                                      'new_mv_line_dicts': []}])
        return res

    def _create_write_off(self):
        # Handle write-off in Payment popup in Invoice/Bill form
        # For invoice, create write-off transaction. For bill, create credit note.

        if not self.env.context.get('active_model', False) == 'account.move':
            return True

        inv_obj = self.env['account.move']
        invoices = inv_obj.browse(self.env.context.get('active_ids')).filtered(lambda x: x.state not in ['draft', 'cancel'])

        for payment in self:
            if payment.payment_writeoff_option == 'reconcile':

                for inv in invoices:
                    reconcile_account_id = inv.partner_id.property_account_receivable_id \
                        if inv.is_sale_document(include_receipts=True) else inv.partner_id.property_account_payable_id
                    description = payment.writeoff_label
                    refund = inv.create_refund(payment.payment_difference, payment.currency_id,
                                               payment.writeoff_account_id, payment.payment_date,
                                               description, inv.journal_id.id)

                    # Put the reason in the chatter
                    subject = 'Write Off An Account'
                    body = description
                    refund.message_post(body=body, subject=subject)

                    # validate, reconcile and stay on invoice form.
                    to_reconcile_lines = inv.line_ids.filtered(lambda line:
                                                               line.account_id.id == reconcile_account_id.id)
                    refund.action_post()  # validate write-off
                    to_reconcile_lines += refund.line_ids.filtered(lambda line:
                                                                   line.account_id.id == reconcile_account_id.id)
                    to_reconcile_lines.filtered(lambda l: not l.reconciled).reconcile()

    def action_validate_invoice_payment(self):
        res = super(AccountPaymentUSA, self).action_validate_invoice_payment()

        for payment in self:
            invoice = payment.invoice_ids
            if invoice.ar_in_charge:
                payment.ar_in_charge = invoice.ar_in_charge
            elif invoice.partner_id.ar_in_charge:
                payment.ar_in_charge = invoice.partner_id.ar_in_charge

        return res

    def delete_payment(self):
        self.unlink()
        return {'type': 'ir.actions.client', 'tag': 'history_back'}

    def action_draft(self):
        self.write({"has_been_voided": False})
        super(AccountPaymentUSA, self.with_context(from_payment=self.ids)).action_draft()

    def action_draft_usa(self):
        self.ensure_one()
        action = self.env.ref('l10n_us_accounting.action_view_button_set_to_draft_message').read()[0]
        action['context'] = isinstance(action.get('context', {}), dict) or {}
        action['context']['default_payment_id'] = self.id
        return action

    def unlink(self):
        if self.env.context.get('force_unlink', False):
            for record in self:
                record.move_name = False
        return super(AccountPaymentUSA, self).unlink()

    @api.depends('partner_id', 'currency_id')
    def _get_has_open_invoice(self):
        """
        To show or hide Open invoices section
        """
        for record in self:
            record.has_open_invoice = False

            if record.partner_id:
                domain = self._get_available_aml_domain(record)
                lines = self.env['account.move.line'].search(domain)
                if lines:
                    record.has_open_invoice = True

    @api.depends('partner_id', 'open_invoice_ids', 'state', 'currency_id')
    def _get_available_move_line(self):
        """
        Get available open invoices to add.
        """
        for record in self:
            if record.partner_id:
                added_ids = [line.account_move_line_id.id for line in record.open_invoice_ids]  # aml already added

                domain = [('id', 'not in', added_ids)]
                domain = self._get_available_aml_domain(record, domain)
                lines = self.env['account.move.line'].search(domain)
                record.available_move_line_ids = [(6, 0, lines.ids)]
            else:
                record.available_move_line_ids = False

    def _get_available_aml_domain(self, record, domain=None):
        domain = domain if domain else []
        partner_id = self.env['res.partner']._find_accounting_partner(record.partner_id)
        domain.extend([
            ('account_id', '=', record.destination_account_id.id),
            ('reconciled', '=', False),
            '|', ('partner_id', '=', partner_id.id), ('partner_id', '=', False),
            '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ('parent_state', '=', 'posted')
        ])

        # Find aml that have same currency with payment
        company_currency = record.company_id.currency_id if record.company_id else self.env.company.currency_id
        if not record.currency_id == company_currency:
            domain.extend([('currency_id', '=', record.currency_id.id)])
        else:
            domain.extend([('currency_id', '=', False)])

        if record.payment_type == 'inbound':  # customer payment
            domain.extend([('credit', '=', 0), ('debit', '>', 0)])
        elif record.payment_type == 'outbound':  # bill payment
            domain.extend([('credit', '>', 0), ('debit', '=', 0)])

        return domain

    @api.onchange('partner_id', 'currency_id')
    def _update_open_invoice_ids(self):
        self.open_invoice_ids = [(5,)]

    def action_void(self):
        action = self.env.ref('account.action_view_account_move_reversal').read()[0]
        return action

    # CHECK PRINTING
    def _check_make_stub_line(self, invoice):
        res = super()._check_make_stub_line(invoice)

        # Get Credit/Discount Amount
        credit_amount = other_payment_amount = 0
        amount_field = 'amount_currency' if self.currency_id != self.journal_id.company_id.currency_id else 'amount'
        # Looking for Vendor Credit Note in Vendor Bill
        if invoice.type in ['in_invoice', 'out_refund']:
            # This is for Vendor Bill only
            credit_note_ids = invoice.line_ids.mapped('matched_debit_ids').filtered(
                lambda r: r.debit_move_id.move_id.type == 'in_refund')
            credit_amount = abs(sum(credit_note_ids.mapped(amount_field)))

            # Calculate Other Payment amount
            other_payment_ids = invoice.line_ids.mapped('matched_debit_ids').filtered(
                lambda r: r.debit_move_id not in self.move_line_ids and r.id not in credit_note_ids.ids)
            other_payment_amount = abs(sum(other_payment_ids.mapped(amount_field)))

        # Update Amount Residual, BEFORE apply this check
        amount_residual = invoice.amount_total - other_payment_amount

        res.update({'credit_amount': formatLang(self.env, credit_amount, currency_obj=invoice.currency_id),
                    'amount_residual': formatLang(self.env, amount_residual,
                                                  currency_obj=invoice.currency_id) if amount_residual * 10 ** 4 != 0 else '-'
                    })

        return res

    def _check_build_page_info(self, i, p):
        res = super()._check_build_page_info(i, p)

        if self.partner_id.print_check_as and self.partner_id.check_name:
            res['partner_name'] = self.partner_id.check_name

        return res

    # Payment receipt
    @api.depends('invoice_ids', 'payment_type', 'partner_type', 'partner_id')
    def _compute_destination_account_id(self):
        payment_receipts = self.filtered('is_payment_receipt')
        for record in payment_receipts:
            if record.partner_type == 'customer':
                record.destination_account_id = record.income_account.id
            else:
                record.destination_account_id = record.expense_account.id

        super(AccountPaymentUSA, self - payment_receipts)._compute_destination_account_id()

    ####################################################
    # CRUD methods
    ####################################################
    @api.model
    def create(self, values):
        payment = super(AccountPaymentUSA, self).create(values)
        if not payment.ar_in_charge and payment.partner_id.ar_in_charge:
            payment.ar_in_charge = payment.partner_id.ar_in_charge
        return payment

    def _init_column(self, column_name):
        if column_name == 'has_open_invoice':
            posted_payments = self.sudo().search([('state', 'not in', ['draft', 'cancelled']),
                                                  ('payment_type', '!=', 'transfer')])

            query = """INSERT INTO usa_payment_invoice (payment_id, account_move_line_id, payment)
                      VALUES (%(payment_id)s, %(move_line_id)s, %(payment_amount)s)"""
            query_list = []
            for payment in posted_payments:
                receivable_lines = payment.move_line_ids.filtered(lambda x: x.account_id.internal_type == 'receivable')
                payable_lines = payment.move_line_ids.filtered(lambda x: x.account_id.internal_type == 'payable')

                if receivable_lines:
                    matched_debit_ids = receivable_lines.mapped('matched_debit_ids')
                    query_list.extend([{'payment_id': payment.id, 'move_line_id': debit.debit_move_id.id,
                                        'payment_amount': debit.amount}
                                       for debit in matched_debit_ids])
                if payable_lines:
                    matched_credit_ids = payable_lines.mapped('matched_credit_ids')
                    query_list.extend([{'payment_id': payment.id, 'move_line_id': credit.credit_move_id.id,
                                        'payment_amount': credit.amount}
                                       for credit in matched_credit_ids])
            if query_list:
                self.env.cr._obj.executemany(query, query_list)
                self.env.cr.commit()

        else:
            super(AccountPaymentUSA, self)._init_column(column_name)
