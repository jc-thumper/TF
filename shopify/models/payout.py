from odoo import models, fields, _
from datetime import timedelta, datetime
from .misc import convert_shopify_datetime_to_utc


class ShopifyPayout(models.Model):
    _name = "shopify.payout"
    _description = "Shopify Payout"

    name = fields.Char('Name', required=True, copy=False, index=True, default=lambda self: _('New'))
    report_id = fields.Char("Shopify Payout ID", copy=False)
    mk_instance_id = fields.Many2one('mk.instance', "Instance", copy=False)
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('partially_processed', 'Partially Processed'), ('done', 'Done'), ('settled', 'Settled')],
                             string="Status", default="draft")
    currency_id = fields.Many2one('res.currency', string="Currency", copy=False)
    payout_date = fields.Date("Payout Date", help="The date when the payout was issued.")
    payout_line_ids = fields.One2many('shopify.payout.line', 'payout_id')
    amount = fields.Float("Amount", help="The total amount of the payout.")
    bank_statement_id = fields.Many2one('account.bank.statement')

    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('shopify.payout') or _('New')
        res = super(ShopifyPayout, self).create(vals)
        return res

    def fetch_payout_from_shopify(self, mk_instance_id):
        request_url = '/admin/api/2020-01/shopify_payments/payouts.json'
        end_date = fields.Date.to_string(datetime.now())
        if mk_instance_id.payout_report_last_sync_date:
            start_date = fields.Date.to_string(mk_instance_id.payout_report_last_sync_date)
        else:
            start_date = fields.Date.to_string(datetime.now() - timedelta(days=365))
        params = {'date_min': start_date, 'date_max': end_date, 'status': 'paid', 'limit': mk_instance_id.api_limit}
        payout_list, next_url = [], False
        while 1:
            if next_url:
                params = {}
            response = mk_instance_id.shopify_api_call('GET', request_url, params=params, full_url=next_url)
            payout_list += response.json().get('payouts', [])
            next_url = response.links.get('next', {}).get('url', '')
            if not next_url:
                break

        return payout_list, start_date, end_date

    def fetch_transaction_of_payout(self, mk_instance_id, payout_id):
        request_url = '/admin/api/2020-01/shopify_payments/balance/transactions.json'
        params = {'payout_id': payout_id, 'limit': mk_instance_id.api_limit}
        transaction_list, next_url = [], False
        while 1:
            if next_url:
                params = {}
            response = mk_instance_id.shopify_api_call('GET', request_url, params=params, full_url=next_url)
            transaction_list += response.json().get('transactions', [])
            next_url = response.links.get('next', {}).get('url', '')
            if not next_url:
                break

        return transaction_list

    def create_bank_statement(self, mk_instance_id, payout_id, end_date, statement_line_list):
        bank_statement_obj = self.env['account.bank.statement']
        name = '{} [{}] [{}]'.format(mk_instance_id.name, payout_id.payout_date, payout_id.report_id)
        vals = {'name': name,
                'shopify_ref': payout_id.report_id,
                'journal_id': mk_instance_id.payout_journal_id.id,
                'date': end_date,
                'currency_id': payout_id.currency_id.id,
                'line_ids': statement_line_list,
                'balance_end_real': payout_id.amount}
        statement_id = bank_statement_obj.create(vals)
        return statement_id

    def prepare_bank_statement_line(self, payout_id):
        bank_statement_line_list = []
        for payout_line_id in payout_id.payout_line_ids:
            order_id = self.env['sale.order'].search([('mk_id', '=', payout_line_id.source_order_id)])
            bank_statement_line_list.append((0, 0, {'name': payout_line_id.source_type,
                                                    'ref': payout_line_id.transaction_id,
                                                    'amount': payout_line_id.amount,
                                                    'date': payout_line_id.processed_at,
                                                    'currency_id': payout_id.currency_id.id,
                                                    'shopify_order_id': order_id.id or False}))
        return bank_statement_line_list

    def shopify_import_payout_report(self, mk_instance_id):
        currency_obj = self.env['res.currency']
        mk_instance_id = self.env['mk.instance'].sudo().browse(mk_instance_id)
        payout_list, start_date, end_date = self.fetch_payout_from_shopify(mk_instance_id)
        for payout_dict in payout_list:
            payout_id = payout_dict.get('id')
            payout_currency_id = currency_obj.search([('name', '=', payout_dict.get('currency'))], limit=1)
            if not payout_currency_id:
                break
            existing_payout_id = self.search([('report_id', '=', payout_id), ('mk_instance_id', '=', mk_instance_id.id)])
            if existing_payout_id:
                continue
            payout_vals = {'report_id': payout_id,
                           'currency_id': payout_currency_id.id,
                           'payout_date': convert_shopify_datetime_to_utc(payout_dict.get('date')),
                           'amount': payout_dict.get('amount'),
                           'mk_instance_id': mk_instance_id.id}
            transaction_list = self.fetch_transaction_of_payout(mk_instance_id, payout_id)
            transaction_vals_list = []
            for transaction_dict in transaction_list:
                if transaction_dict.get('source_type') == 'payout':
                    continue
                transaction_currency_id = currency_obj.search([('name', '=', transaction_dict.get('currency'))], limit=1)
                if not transaction_currency_id:
                    break
                transaction_vals_list.append((0, 0, {'transaction_id': transaction_dict.get('id'),
                                                     'currency_id': transaction_currency_id.id,
                                                     'amount': transaction_dict.get('amount'),
                                                     'fee': transaction_dict.get('fee'),
                                                     'source_order_id': transaction_dict.get('source_order_id'),
                                                     'source_type': transaction_dict.get('source_type'),
                                                     'processed_at': convert_shopify_datetime_to_utc(transaction_dict.get('processed_at'))}))
            payout_vals['payout_line_ids'] = transaction_vals_list
            payout_id = self.create(payout_vals)
            statement_line_list = self.prepare_bank_statement_line(payout_id)
            statement_id = self.create_bank_statement(mk_instance_id, payout_id, end_date, statement_line_list)
            payout_id.bank_statement_id = statement_id.id
        mk_instance_id.payout_report_last_sync_date = end_date
        return True

    def shopify_process_payout_report(self, mk_instance_id):
        mk_instance_id = self.env['mk.instance'].sudo().browse(mk_instance_id)
        payout_ids = self.search([('mk_instance_id', '=', mk_instance_id.id), ('report_id', '!=', False), ('state', 'in', ['draft', 'in_progress', 'partially_processed'])])
        for payout_id in payout_ids:
            if payout_id.bank_statement_id.state != 'open':
                return True
            payout_id.reconcile_transactions(payout_id.bank_statement_id)
        return True

    def reconcile_transactions(self, statement_id):
        invoices, move_line_obj = self.env['account.invoice'], self.env['account.move.line']
        for line_id in statement_id.line_ids:
            order_id = line_id.shopify_order_id
            if order_id:
                invoices += order_id.invoice_ids
                invoices = invoices.filtered(lambda record: record.type == 'out_invoice' and record.state == 'open')
                account_move_ids = list(map(lambda x: x.move_id.id, invoices))
                move_lines = move_line_obj.search([('move_id', 'in', account_move_ids), ('user_type_id.type', '=', 'receivable'), ('reconciled', '=', False)])
                mv_line_dicts = []
                move_line_total_amount = 0.0
                currency_ids = []
                for moveline in move_lines:
                    amount = moveline.debit - moveline.credit
                    amount_currency = 0.0
                    if moveline.amount_currency:
                        currency, amount_currency = self.convert_move_amount_currency(statement_id, moveline, amount)
                        if currency:
                            currency_ids.append(currency)

                    if amount_currency:
                        amount = amount_currency
                    mv_line_dicts.append({
                        'credit': abs(amount) if amount > 0.0 else 0.0,
                        'name': moveline.invoice_id.number,
                        'move_line': moveline,
                        'debit': abs(amount) if amount < 0.0 else 0.0
                    })
                    move_line_total_amount += amount
                if round(line_id.amount, 10) == round(move_line_total_amount, 10) and (not line_id.currency_id or line_id.currency_id.id == line_id.currency_id.id):
                    if currency_ids:
                        currency_ids = list(set(currency_ids))
                        if len(currency_ids) == 1:
                            line_id.write({'amount_currency': move_line_total_amount, 'currency_id': currency_ids[0]})
                    line_id.process_reconciliation(mv_line_dicts)
            if not line_id.search([('journal_entry_ids', '=', False), ('statement_id', '=', statement_id.id)]):
                self.write({'state': 'processed'})
            elif line_id.search([('journal_entry_ids', '!=', False), ('statement_id', '=', statement_id.id)]):
                if self.state != 'partially_processed':
                    self.write({'state': 'partially_processed'})
        return True

    def convert_move_amount_currency(self, bank_statement, moveline, amount):
        amount_currency = 0.0
        if moveline.company_id.currency_id.id != bank_statement.currency_id.id:
            # In the specific case where the company currency and the statement currency are the same
            # the debit/credit field already contains the amount in the right currency.
            # We therefore avoid to re-convert the amount in the currency, to prevent Gain/loss exchanges
            amount_currency = moveline.currency_id._convert(moveline.amount_currency, bank_statement.currency_id, self.env.user.company_id, fields.Date.today())
        elif moveline.invoice_id and moveline.invoice_id.currency_id.id != bank_statement.currency_id.id:
            amount_currency = moveline.invoice_id.currency_id._convert(amount, bank_statement.currency_id, self.env.user.company_id, fields.Date.today())
        currency = moveline.currency_id.id
        return currency, amount_currency

    def process_payout(self):
        self.reconcile_transactions(self.bank_statement_id)
        return True


class ShopifyPayoutLine(models.Model):
    _name = "shopify.payout.line"
    _description = "Shopify Payout Line"

    payout_id = fields.Many2one("shopify.payout", "Payout")
    transaction_id = fields.Char("Transaction ID")
    currency_id = fields.Many2one('res.currency', string="Currency")
    amount = fields.Float("Amount")
    fee = fields.Float("Fees")
    source_order_id = fields.Char("Source Order ID", help="The id of the Order that this transaction ultimately originated from.")
    source_type = fields.Char("Source Type", help="The type of the resource leading to the transaction.")
    processed_at = fields.Datetime("Processed Date", help="The time the transaction was processed.")
