# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.model_const import ACCOUNT_JOURNAL


class AccountJournalUSA(models.Model):
    _inherit = 'account.journal'

    is_credit_card = fields.Boolean(string='Credit Card')

    partner_id = fields.Many2one('res.partner', string='Vendor',
                                help='This contact will be used to record vendor bill and payment '
                                     'for credit card balance.',
                                copy=False)

    def _default_inbound_payment_methods(self):
        """
        Set Electronic as default Debit Method
        """
        vals = super(AccountJournalUSA, self)._default_inbound_payment_methods()
        return vals + self.env.ref('payment.account_payment_method_electronic_in')

    write_off_sequence_id = fields.Many2one('ir.sequence', string='Credit Note Entry Sequence',
                                            help='This field contains the information related to the numbering of '
                                                 'the write off entries of this journal.',
                                            copy=False)

    write_off_sequence_number_next = fields.Integer(string='Write Off: Next Number',
                                                    help='The next sequence number will be used for the next write off.',
                                                    compute='_compute_write_off_seq_number_next',
                                                    inverse='_inverse_write_off_seq_number_next')

    # do not depend on 'write_off_sequence_id.date_range_ids', because
    # write_off_sequence_id._get_current_sequence() may invalidate it!
    @api.depends('write_off_sequence_id.use_date_range', 'write_off_sequence_id.number_next_actual')
    def _compute_write_off_seq_number_next(self):
        """
        Compute 'sequence_number_next' according to the current sequence in use,
        an ir.sequence or an ir.sequence.date_range.
        """
        for journal in self:
            if journal.write_off_sequence_id:
                sequence = journal.write_off_sequence_id._get_current_sequence()
                journal.write_off_sequence_number_next = sequence.number_next_actual
            else:
                journal.write_off_sequence_number_next = 1

    def _inverse_write_off_seq_number_next(self):
        """
        Inverse 'write_off_sequence_number_next' to edit the current sequence next number.
        """
        for journal in self:
            if journal.write_off_sequence_id and journal.write_off_sequence_number_next:
                sequence = journal.write_off_sequence_id._get_current_sequence()
                sequence.number_next = journal.write_off_sequence_number_next

    def write(self, vals):
        result = super(AccountJournalUSA, self).write(vals)

        # create the relevant write off sequence
        for journal in self.filtered(lambda j: j.type in ('sale') and not j.write_off_sequence_id):
            journal_vals = {
                'name': journal.name,
                'company_id': journal.company_id.id,
                'code': journal.code,
                'write_off_sequence_number_next': vals.get('write_off_sequence_number_next',
                                                           journal.write_off_sequence_number_next),
            }
            journal.write_off_sequence_id = self.sudo()._create_write_off_sequence(journal_vals).id

        return result

    @api.model
    def _create_write_off_sequence(self, vals):
        """ Create new no_gap entry sequence for every new Journal"""

        seq = {
            'name': vals['name'] + ': Write Off',
            'implementation': 'no_gap',
            'prefix': vals['code'] + '/%(range_year)s/',
            'padding': 4,
            'number_increment': 1,
            'use_date_range': True,
        }
        if 'company_id' in vals:
            seq['company_id'] = vals['company_id']
        seq = self.env['ir.sequence'].create(seq)
        seq_date_range = seq._get_current_sequence()

        # Create a new sequence of write off
        seq_date_range.number_next = vals.get('write_off_sequence_number_next', 1)
        return seq

    @api.model
    def create(self, vals):
        if vals.get('type') == 'sale' and not vals.get('write_off_sequence_id'):
            vals['write_off_sequence_id'] = self.sudo()._create_write_off_sequence(vals).id

        if vals.get('is_credit_card'):
            company_id = vals.get('company_id', self.env.company.id)
            # Create a default debit/credit account if not given
            default_account = vals.get('default_debit_account_id') or vals.get('default_credit_account_id')
            if not default_account:
                company = self.env['res.company'].browse(company_id)
                account_vals = self._prepare_credit_card_account(vals.get('name'), company, vals.get('currency_id'),
                                                                 vals.get('type'))
                default_account = self.env['account.account'].create(account_vals)
                vals['default_debit_account_id'] = default_account.id
                vals['default_credit_account_id'] = default_account.id

        return super(AccountJournalUSA, self).create(vals)

    @api.model
    def _prepare_credit_card_account(self, name, company, currency_id, type):
        account_vals = self._prepare_liquidity_account(name, company, currency_id, type)
        credit_card_type = self.env.ref('account.data_account_type_credit_card')
        account_vals['user_type_id'] = credit_card_type and credit_card_type.id or False
        return account_vals

    @api.model
    def update_sequences(self, account_journal_name, account_journal_code, old_pattern, new_pattern):
        # only override this config at the first time when install or upgrade module
        account_journal = self.env[ACCOUNT_JOURNAL].search(['|', ('name', '=', account_journal_name),
                                                            ('code', '=', account_journal_code)])
        if not account_journal:
            raise UserError('Please config account journal of %s ' % account_journal_name)

        for journal in account_journal:
            journal.refund_sequence = True

            # Change the sequence number format
            sequence_obj = journal.refund_sequence_id
            sequence_obj.prefix = sequence_obj.prefix.replace(old_pattern, new_pattern)

    @api.model
    def create_write_off_sequences(self, account_journal_name, account_journal_code, write_off_sequence_number_next, code):
        # only create this config at the first time when install or upgrade module
        account_journal = self.env[ACCOUNT_JOURNAL].search([('name', '=', account_journal_name),
                                                            ('code', '=', account_journal_code)])
        if not account_journal:
            raise UserError('Please config account journal of {} '.format(account_journal_name))

        for journal in account_journal:
            journal_vals = {
                'name': journal.name,
                'company_id': journal.company_id.id,
                'code': code,
                'write_off_sequence_number_next': write_off_sequence_number_next,
            }
            journal.write_off_sequence_id = self._create_write_off_sequence(journal_vals).id

    def open_action_with_context(self):
        action = super(AccountJournalUSA, self).open_action_with_context()

        context = action['context']
        if context.get('default_journal_id', False):
            del context['default_journal_id']

        if self.env.context.get('use_domain', False):
            action['domain'] = ['|', ('match_journal_ids', 'in', [self.id]), ('match_journal_ids', '=', False)]

        action['context'] = context
        return action
