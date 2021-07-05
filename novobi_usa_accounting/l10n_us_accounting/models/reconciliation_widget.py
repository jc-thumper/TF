from odoo import fields, models, api
from odoo.osv import expression


class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    @api.model
    def get_bank_statement_data(self, bank_statement_line_ids, srch_domain=[]):
        """
        Override.
        Called when load reviewed form.
        Add status = open to `domain` in order to remove excluded/reconciled bank statement lines.
        :param bank_statement_line_ids:
        :param srch_domain:
        :return:
        """
        srch_domain.append(('status', '=', 'open'))
        return super(AccountReconciliation, self).get_bank_statement_data(bank_statement_line_ids, srch_domain)

    @api.model
    def get_batch_payments_data(self, bank_statement_ids):
        """
        Override from widget_reconciliation of account_batch_payment.
        Only show batch payments containing payments which have not been reviewed yet.
        :param bank_statement_ids
        :return: batch_payments (after filter)
        """
        batch_payments = super(AccountReconciliation, self).get_batch_payments_data(bank_statement_ids)

        env = self.env['account.batch.payment']
        length = len(batch_payments)
        index = 0

        while index < length:
            batch = batch_payments[index]
            batch_id = env.browse(batch['id'])
            move_lines = batch_id.get_batch_payment_aml().filtered(lambda r: not r.statement_line_id)
            if move_lines:
                # Re-calculate amount of this batch payment, because its payments may be applied for another BSL before.
                batch.update(batch_id._get_batch_info_for_review())
                index += 1
            else:
                del batch_payments[index]
                length -= 1

        return batch_payments

    @api.model
    def get_move_lines_by_batch_payment(self, st_line_id, batch_payment_id):
        """
        Override Odoo's.
        Also get move lines for adjustments.
        """
        st_line = self.env['account.bank.statement.line'].browse(st_line_id)
        batch_id = self.env['account.batch.payment'].browse(batch_payment_id)

        move_lines = batch_id.get_batch_payment_aml().filtered(lambda r: not r.statement_line_id)

        target_currency = st_line.currency_id or st_line.journal_id.currency_id or st_line.journal_id.company_id.currency_id
        return self._prepare_move_lines(move_lines, target_currency=target_currency, target_date=st_line.date)

    @api.model
    def process_bank_statement_line(self, st_line_ids, data):
        """
        Override.
        Called when clicking on button `Apply` on `bank_statement_reconciliation_view` (review screen)
        :param st_line_ids:
        :param data:
        :return:
        """
        # Assign status='confirm' for reviewed bank_statement_line
        st_values = {'status': 'confirm'}

        # If payee_id in context (apply bank rule condition), payee will be written to partner_id of account move line,
        # but not bank statement line.
        payee_id = self._context.get('payee_id', False)
        if payee_id and data:
            data[0]['partner_id'] = payee_id
            st_values['partner_id'] = False

        result = super(AccountReconciliation, self).process_bank_statement_line(st_line_ids, data)
        self.env['account.bank.statement.line'].browse(st_line_ids).write(st_values)

        processed_moves = result.get('moves', [])
        aml_ids = self.env['account.move'].browse(processed_moves).mapped('line_ids').filtered('statement_line_id')

        # Assign temporary_reconciled=True for reviewed account_move_line.
        aml_ids.write({'temporary_reconciled': True})

        # Assign state='posted' for payment accounts which are just reviewed.
        aml_ids.mapped('payment_id').write({'state': 'posted'})

        return result

    @api.model
    def _domain_move_lines_for_reconciliation(self, st_line, aml_accounts, partner_id, excluded_ids=[], search_str=False, mode='rp'):
        """
        Override.
        Filter and remove account_move_lines (for both invoice/bill and payment) suggested in review form, if:
            - belong to payment and has account_id = AR/AP
            - credit/debit >= amount of st_line
            - be on the same side with amount of st_line
        :param st_line: account.bank.statement.line record
        :param aml_accounts:
        :param partner_id:
        :param excluded_ids:
        :param search_str:
        :param mode: 'rp' or 'other', each st_line in review form will call get_move_lines_for_bank_statement_line
            2 times, once for 'rp' (Customer/Vendor Matching tab) and once for 'other' (Miscellaneous Matching tab).

        ** For 'rp':
            INVOICE:
                + Debit     ->  Account Receivable  (type = 'receivable')   <= Review this line.
                + Credit    ->  Product Sales       (type = others)
            BILL:
                + Debit     ->  Expenses            (type = others)
                + Credit    ->  Account Payable     (type = 'payable')      <= Review this line.
            CUSTOMER PAYMENT/DEPOSIT:
                + Debit     ->  Bank                (type = 'liquidity')    <= Review this line.
                + Credit    ->  Account Receivable  (type = 'receivable')   or  Customer Deposit    (type = others)
            VENDOR PAYMENT/DEPOSIT:
                + Debit     ->  Account Payable     (type = 'payable')      or  Prepayments         (type = others)
                + Credit    ->  Bank                (type = 'liquidity')    <= Review this line.
            JOURNAL ENTRY: will review:
                + Bank (different from Odoo)
                + Account Receivable/Account Payable

        ** For 'other': will NOT review:
            INVOICE/BILL (Product Sales, Expenses...).
            PAYMENT (Account Receivable/Payable, Prepayments...).

        :return: domain
        """
        domain = super(AccountReconciliation, self)._domain_move_lines_for_reconciliation(
            st_line, aml_accounts, partner_id, excluded_ids, search_str, mode)

        # Bank line in JE should be able to reviewed (By default Odoo rejects it)
        remove_cond = ('payment_id', '<>', False)
        for index in range(len(domain)):
            if domain[index] == remove_cond:
                domain[index] = ('payment_id', '<>', -1)    # Replace by a tautology but cannot remove because '&' is still in domain.
                break

        if mode == 'rp':
            # Invoice/Bill: internal_type in ['receivable', 'payable', 'liquidity'] (Odoo OOTB).
            # Payment/Deposit, internal_type in ['liquidity'].
            domain = expression.AND([domain, [
                '&',
                    '|',    # If account is Bank (liquidity), it must match with bank account of this BSL journal.
                        ('account_id.internal_type', '!=', 'liquidity'),
                        '&', ('account_id.internal_type', '=', 'liquidity'), ('account_id', 'in', aml_accounts),
                    '|',    # If it belongs to payment, only get Bank line.
                        ('payment_id', '=', False),
                        '&', ('payment_id', '!=', False), ('account_id.internal_type', '=', 'liquidity')
            ]])
        else:
            # Only apply for Journal Entry and must match with Bank Account.
            domain = expression.AND([domain, [
                ('payment_id', '=', False),
                ('move_id.type', '=', 'entry')
            ]])

        domain = expression.AND([domain, [
            ('bank_reconciled', '=', False),
            ('date', '<=', st_line.date),
            '|',
                '&', ('debit', '=', 0), ('credit', '<=', -st_line.amount),
                '&', ('credit', '=', 0), ('debit', '<=', st_line.amount),
        ]])

        return domain
