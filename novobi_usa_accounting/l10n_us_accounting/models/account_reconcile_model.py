# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_is_zero

import re

from ..models.model_const import (
    ACCOUNT_BANK_STATEMENT_LINE,
)

USA_PARTNER_TYPE = {
    'amount_received': ['customer', 'both'],
    'amount_paid': ['supplier', 'both'],
    'both': ['customer', 'supplier', 'both']
}


# TODO: Review new conditions in v12
class AccountReconcileModelUSA(models.Model):
    _inherit = 'account.reconcile.model'
    _order = 'sequence, id'

    # Override
    name = fields.Char(string='Rule')
    rule_type = fields.Selection(selection=[
        ('writeoff_button', 'Manually create a write-off on clicked button.'),
        ('writeoff_suggestion', 'Suggest counterpart values.'),
        ('invoice_matching', 'Match existing transactions.')
    ], string='Type', default='writeoff_suggestion', required=True)
    has_second_line = fields.Boolean(string='Include multiple rules?')
    label = fields.Char(string='Memo')
    # amount_type is not required since it is moved to account.reconcile.model.line
    amount_type = fields.Selection(required=False)
    amount = fields.Float(required=False)

    # New fields
    payee_id = fields.Many2one('res.partner', string='Payee')
    line_ids = fields.One2many('account.reconcile.model.line', 'line_id', string='Bank rule lines', copy=True)

    @api.onchange('match_nature')
    def _onchange_match_nature(self):
        return {
            'domain': {
                'payee_id': [
                    ('parent_id', '=', False),
                    ('usa_partner_type', 'in', USA_PARTNER_TYPE.get(self.match_nature, []))
                ]
            }
        }

    @api.onchange('has_second_line')
    def _onchange_has_second_line(self):
        if not self.has_second_line:
            self.line_ids = None
        else:
            self.account_id = self.analytic_account_id = self.analytic_tag_ids = None

    @api.onchange('amount_type')
    def _onchange_amount_type(self):
        if self.line_ids:
            if self.amount_type == 'percentage':
                for line_id in self.line_ids:
                    line_id.amount = 0
            elif self.amount_type == 'fixed':
                for line_id in self.line_ids:
                    line_id.amount_percentage = 0

    @api.constrains('line_ids', 'has_second_line')
    def _check_amount(self):
        for record in self:
            if record.has_second_line and not record.line_ids:
                raise ValidationError(_('Please add at least one line item for this rule'))

    @api.model
    def create(self, values):
        self.env.cr.execute("""SELECT max(sequence) + 1 as max_sequence FROM account_reconcile_model;""")
        max_sequence = self.env.cr.dictfetchall()[0]
        if max_sequence.get('max_sequence'):
            values['sequence'] = max_sequence.get('max_sequence')
        result = super(AccountReconcileModelUSA, self).create(values)

        return result

    def _get_write_off_move_lines_dict(self, st_line, move_lines=None):
        """
        Override from odoo.
        Allow to create aml_dicts (to be passed to the create()) corresponding to the reconciliation model's write-off
        lines based on multiple bank rule lines.
        :param st_line: An account.bank.statement.line record.
        :param move_lines: An account.move.line recordset.
        :return: A list of dict representing move.lines to be created corresponding to the write-off lines.
        """
        def get_line_balance(balance, line, multiple):
            # Calculate balance of this line based on remaining balance.
            if line.amount_type == 'fixed':
                return (line.amount_fixed if multiple else line.amount) * (1 if balance > 0.0 else -1)
            elif line.amount_type == 'percentage':
                return balance * ((line.amount_percentage if multiple else line.amount) / 100.0)
            else:
                match = re.search(line.amount_regex if multiple else line.amount_from_label_regex, st_line.name)
                value = re.sub(r'\D' + line.decimal_separator, '', match.group(1)).replace(line.decimal_separator, '.') if match else 0
                return float(value) * (1 if balance > 0.0 else -1)

        def append_to_new_aml_dict(balance, new_aml_dicts, line, multiple=False):
            # Create writeoff for this line and append to new_aml_dicts
            line_balance = get_line_balance(balance, line, multiple)
            writeoff_line = {
                'name': line.label or st_line.name,
                'account_id': line.account_id.id,
                'analytic_account_id': line.analytic_account_id.id,
                'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                'debit': line_balance > 0 and line_balance or 0,
                'credit': line_balance < 0 and -line_balance or 0,
                'reconcile_model_id': line.id,
            }
            new_aml_dicts.append(writeoff_line)

            if line.tax_ids:
                writeoff_line['tax_ids'] = [(6, None, line.tax_ids.ids)]
                tax = line.tax_ids
                # Multiple taxes with force_tax_included results in wrong computation, so we
                # only allow to set the force_tax_included field if we have one tax selected
                if line.force_tax_included:
                    tax = tax[0].with_context(force_price_include=True)
                new_aml_dicts += self._get_taxes_move_lines_dict(tax, writeoff_line)

        self.ensure_one()
        if self.rule_type == 'invoice_matching' and (not self.match_total_amount or (self.match_total_amount_param == 100)):
            return []

        line_residual = st_line.currency_id and st_line.amount_currency or st_line.amount
        line_currency = st_line.currency_id or st_line.journal_id.currency_id or st_line.company_id.currency_id
        total_residual = move_lines and sum(aml.currency_id and aml.amount_residual_currency or aml.amount_residual for aml in move_lines) or 0.0

        balance = total_residual - line_residual
        if not (self.has_second_line or self.account_id) or float_is_zero(balance, precision_rounding=line_currency.rounding):
            return []

        new_aml_dicts = []
        if not self.has_second_line:
            append_to_new_aml_dict(balance, new_aml_dicts, self)
        else:
            for line in self.line_ids:
                remaining_balance = balance - sum(aml['debit'] - aml['credit'] for aml in new_aml_dicts)
                append_to_new_aml_dict(remaining_balance, new_aml_dicts, line, multiple=True)

        return new_aml_dicts

    def _apply_conditions(self, query, params):
        """
        Apply payee condition to bank rule for invoice_matching and writeoff_suggestion, if this bank rule is set payee.
        - Invoice matching: account_move_line having same partner_id to payee, or no partner_id, will be suggested for
        this bank_statement_line.
        - Writeoff suggestion: if this bank_statement_line having same partner_id to payee, or no partner_id,
        account_move_line will be created automatically, and payee will be written to partner_id of account_move_line,
        but not bank_statement_line.
        :param query:
        :param params:
        :return: (query, params)
        """
        self.ensure_one()
        query, params = super(AccountReconcileModelUSA, self)._apply_conditions(query, params)
        payee_id = self.payee_id and self.payee_id.id or False

        if self.rule_type == 'invoice_matching':
            select = """
            AS aml_date_maturity,
            aml.date AS aml_date,
            CASE WHEN st_line.check_number_cal IS NOT NULL AND st_line.check_number_cal = payment.check_number_text THEN 1 ELSE 0 END AS match_check,
            """

            join = """
            LEFT JOIN account_payment payment ON payment.id = aml.payment_id
            LEFT JOIN account_payment_method payment_method ON payment_method.id = payment.payment_method_id
            LEFT JOIN account_move move
            """

            where = """
            AND (
                payment.id IS NOT NULL                              -- If payment:
                AND account.internal_type = 'liquidity'                 -- Only Choose Bank line
                AND aml.journal_id = st_line.journal_id                 -- Journal must match with BSL
                AND (
                    st_line.check_number_cal IS NULL OR                 -- No check in BSL name -> whatever
                    payment_method.name != 'Checks' OR                  -- Not check payment -> whatever
                    (                                                   -- Check number in payment must match with BSL
                        st_line.check_number_cal IS NOT NULL AND
                        payment_method.name = 'Checks' AND
                        payment_method.payment_type = 'outbound' AND
                        payment.check_number_text = st_line.check_number_cal
                    )
                )
                OR payment.id IS NULL                               -- If not payment -> whatever
            )
            AND (                                                   -- If Bank line -> must match with bank account of BSL
                account.internal_type = 'liquidity'
                AND aml.account_id IN (journal.default_credit_account_id, journal.default_debit_account_id)
                OR account.internal_type != 'liquidity'
            )
            AND aml.bank_reconciled IS NOT TRUE                 -- Has not been reconciled
            AND aml.date <= st_line.date                        -- Date < date of BSL
            AND aml.company_id = st_line.company_id
            """

            query = query.replace('AS aml_date_maturity,', select)
            query = query.replace('LEFT JOIN account_move move', join)
            query = query.replace('AND aml.company_id = st_line.company_id', where)

            if payee_id:
                query += ' AND (aml.partner_id IS NULL OR aml.partner_id = {})'.format(payee_id)

        elif self.rule_type == 'writeoff_suggestion' and payee_id:
            query += ' AND (st_line.partner_id IS NULL OR st_line.partner_id = {})'.format(payee_id)

        return query, params

    def _get_invoice_matching_query(self, st_lines, excluded_ids=None, partner_map=None):
        """
        Override Odoo's.
        Get the query applying all rules trying to match existing entries with the given statement lines.
        :param st_lines:        Account.bank.statement.lines recordset.
        :param excluded_ids:    Account.move.lines to exclude.
        :param partner_map:     Dict mapping each line with new partner eventually.
        :return:                (query, params)
        """
        if any(m.rule_type != 'invoice_matching' for m in self):
            raise UserError(_('Programmation Error: Can\'t call _get_invoice_matching_query() for different rules than \'invoice_matching\''))

        queries = []
        all_params = []
        for rule in self:
            # N.B: 'communication_flag' is there to distinguish invoice matching through the number/reference
            # (higher priority) from invoice matching using the partner (lower priority).
            query = r'''
            SELECT
                %s                                  AS sequence,
                %s                                  AS model_id,
                st_line.id                          AS id,
                aml.id                              AS aml_id,
                aml.currency_id                     AS aml_currency_id,
                aml.date_maturity                   AS aml_date_maturity,
                aml.amount_residual                 AS aml_amount_residual,
                aml.amount_residual_currency        AS aml_amount_residual_currency,
                aml.balance                         AS aml_balance,
                aml.amount_currency                 AS aml_amount_currency,
                account.internal_type               AS account_internal_type,

                -- Determine a matching or not with the statement line communication using the aml.name, move.name or move.ref.
                (
                    aml.name IS NOT NULL
                    AND
                    substring(REGEXP_REPLACE(aml.name, '[^0-9|^\s]', '', 'g'), '\S(?:.*\S)*') != ''
                    AND
                        regexp_split_to_array(substring(REGEXP_REPLACE(aml.name, '[^0-9|^\s]', '', 'g'), '\S(?:.*\S)*'),'\s+')
                        && regexp_split_to_array(substring(REGEXP_REPLACE(st_line.name, '[^0-9|^\s]', '', 'g'), '\S(?:.*\S)*'), '\s+')
                )
                OR
                    regexp_split_to_array(substring(REGEXP_REPLACE(move.name, '[^0-9|^\s]', '', 'g'), '\S(?:.*\S)*'),'\s+')
                    && regexp_split_to_array(substring(REGEXP_REPLACE(st_line.name, '[^0-9|^\s]', '', 'g'), '\S(?:.*\S)*'), '\s+')
                OR
                (
                    move.ref IS NOT NULL
                    AND
                    substring(REGEXP_REPLACE(move.ref, '[^0-9|^\s]', '', 'g'), '\S(?:.*\S)*') != ''
                    AND
                        regexp_split_to_array(substring(REGEXP_REPLACE(move.ref, '[^0-9|^\s]', '', 'g'), '\S(?:.*\S)*'),'\s+')
                        && regexp_split_to_array(substring(REGEXP_REPLACE(st_line.name, '[^0-9|^\s]', '', 'g'), '\S(?:.*\S)*'), '\s+')
                )                                   AS communication_flag,
                -- Determine a matching or not with the statement line communication using the move.invoice_payment_ref.
                (
                    move.invoice_payment_ref IS NOT NULL
                    AND
                    regexp_replace(move.invoice_payment_ref, '\s+', '', 'g') = regexp_replace(st_line.name, '\s+', '', 'g')
                )                                   AS payment_reference_flag
            FROM account_bank_statement_line st_line
            LEFT JOIN account_journal journal       ON journal.id = st_line.journal_id
            LEFT JOIN jnl_precision                 ON jnl_precision.journal_id = journal.id
            LEFT JOIN res_company company           ON company.id = st_line.company_id
            LEFT JOIN partners_table line_partner   ON line_partner.line_id = st_line.id
            , account_move_line aml
            LEFT JOIN account_move move             ON move.id = aml.move_id AND move.state = 'posted'
            LEFT JOIN account_account account       ON account.id = aml.account_id
            WHERE st_line.id IN %s
                AND aml.company_id = st_line.company_id
                AND move.state = 'posted'
                AND (
                        -- the field match_partner of the rule might enforce the second part of
                        -- the OR condition, later in _apply_conditions()
                        line_partner.partner_id = 0
                        OR
                        aml.partner_id = line_partner.partner_id
                    )
                AND CASE WHEN st_line.amount > 0.0
                         THEN aml.balance > 0
                         ELSE aml.balance < 0
                    END

                -- if there is a partner, propose all aml of the partner, otherwise propose only the ones
                -- matching the statement line communication
                -- ===============================================================================
                -- !!! REMOVE THIS PART TO APPLY FOR BANK STATEMENT LINE HAVING NO PARTNER ID !!!
                -- ===============================================================================
                
                AND
                (
                    (
                    -- blue lines appearance conditions
                    aml.account_id IN (journal.default_credit_account_id, journal.default_debit_account_id)
                    AND aml.statement_id IS NULL
                    AND (
                        company.account_bank_reconciliation_start IS NULL
                        OR
                        aml.date > company.account_bank_reconciliation_start
                        )
                    )
                    OR
                    (
                    -- black lines appearance conditions
                    account.reconcile IS TRUE
                    AND aml.reconciled IS FALSE
                    )
                )
            '''
            # Filter on the same currency.
            if rule.match_same_currency:
                query += '''
                    AND COALESCE(st_line.currency_id, journal.currency_id, company.currency_id) = COALESCE(aml.currency_id, company.currency_id)
                '''

            params = [rule.sequence, rule.id, tuple(st_lines.ids)]
            # Filter out excluded account.move.line.
            if excluded_ids:
                query += 'AND aml.id NOT IN %s'
                params += [tuple(excluded_ids)]
            query, params = rule._apply_conditions(query, params)
            queries.append(query)
            all_params += params
        full_query = self._get_with_tables(st_lines, partner_map=partner_map)
        full_query += ' UNION ALL '.join(queries)

        # ================== CHANGED PART =======================
        # # Oldest due dates come first.
        # full_query += ' ORDER BY aml_date_maturity, aml_id'
        full_query += """ ORDER BY
            match_check DESC,           -- Chose Check payments first
            aml_date DESC,              -- Closet earlier date with the date of the bank statement line
            aml_date_maturity, aml_id
        """
        # ================== CHANGED PART =======================

        return full_query, all_params


class AccountReconcileModelLine(models.Model):
    _name = 'account.reconcile.model.line'
    _description = 'Preset to create bank rule lines'

    line_id = fields.Many2one('account.reconcile.model', string='Bank rule', index=True, ondelete='cascade')
    company_id = fields.Many2one(related='line_id.company_id')
    currency_id = fields.Many2one('res.currency', string='Account Currency',
                                  default=lambda self: self.env.company.currency_id,
                                  help='Forces all lines for this account to have this account currency.')

    account_id = fields.Many2one('account.account', string='Account', ondelete='cascade', required=True,
                                 domain=[('deprecated', '=', False)])
    journal_id = fields.Many2one('account.journal', string='Journal', ondelete='cascade',
                                 help="This field is ignored in a bank statement reconciliation.")
    label = fields.Char(string='Memo')
    amount_type = fields.Selection(
        [('fixed', 'Amount'), ('percentage', 'Percentage (%)'), ('regex', 'From label')],
        string='Amount Type', default='percentage')

    amount_fixed = fields.Monetary(string='Amount')
    amount_percentage = fields.Float(string='Percentage (%)', digits=0)
    amount_regex = fields.Char(string="Amount from Label (regex)", default=r"([\d\.,]+)")
    decimal_separator = fields.Char(
        default=lambda self: self.env['res.lang']._lang_get(self.env.user.lang).decimal_point,
        help="Every character that is nor a digit nor this separator will be removed from the matching string")

    tax_ids = fields.Many2many('account.tax', string='Taxes', ondelete='restrict')
    force_tax_included = fields.Boolean(string='Tax Included in Price',
                                        help='Force the tax to be managed as a price included tax.')
    show_force_tax_included = fields.Boolean(compute='_compute_show_force_tax_included',
                                             help='Technical field used to show the force tax included button')

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')

    @api.constrains('amount_fixed')
    def _check_amount_fixed(self):
        for record in self:
            if record.amount_type == 'fixed' and record.amount_fixed == 0:
                raise ValidationError(_('Amount must be different from 0.'))

    @api.constrains('amount_percentage')
    def _check_amount_percentage(self):
        for record in self:
            if record.amount_type == 'percentage' and record.amount_percentage == 0:
                raise ValidationError(_('Percentage must be different from 0.'))

    @api.depends('tax_ids')
    def _compute_show_force_tax_included(self):
        for record in self:
            record.show_force_tax_included = False if len(record.tax_ids) != 1 else True

    @api.model
    def read_reconciliation_model_lines(self, line_ids):
        lines = self.search_read(domain=[('id',  'in', line_ids)])
        for line in lines:
            analytic_tags = self.env['account.analytic.tag']\
                .sudo()\
                .search_read(domain=[('id', 'in', line['analytic_tag_ids'])], fields=['id', 'name'])
            line['analytic_tag_ids'] = list(map(lambda e: [e['id'], e['name']], analytic_tags))

        return lines
