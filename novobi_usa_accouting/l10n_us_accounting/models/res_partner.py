# -*- coding: utf-8 -*-
from odoo import api, fields, models

from ..models.model_const import RES_PARTNER, IR_SEQUENCE


class CustomerUSA(models.Model):
    _inherit = 'res.partner'

    country_id = fields.Many2one(default=lambda self: self.env.ref('base.us') and self.env.ref('base.us').id)
    usa_partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Vendor'), ('both', 'Both')], string='Partner Type')
    rec_pay_aml_ids = fields.One2many('account.move.line', 'partner_id',
                                      domain=[('reconciled', '=', False),
                                              ('account_id.internal_type', 'in', ('receivable', 'payable')),
                                              ('move_id.state', '=', 'posted')])

    def _get_ref_next_sequence(self):
        return self.env[IR_SEQUENCE].next_by_code('customer.code')

    ref = fields.Char(string='Code', default=_get_ref_next_sequence, copy=False)

    ar_in_charge = fields.Many2one(string='AR In Charge', comodel_name='res.users')

    # Vendor
    vendor_eligible_1099 = fields.Boolean(string='Vendor Eligible for 1099', default=False)
    print_check_as = fields.Boolean('Print on check as',
                                    help='Check this box if you want to use a different name on checks.')
    check_name = fields.Char('Name on Check')
    debit_overdue_amount = fields.Monetary(compute='_credit_debit_get', string='Debit Overdue Balance', store=True)
    debit_open_balance = fields.Monetary(compute='_credit_debit_get', string='Debit Open Balance', store=True)

    # Customer
    overdue_amount = fields.Monetary(compute='_credit_debit_get', string='Credit Overdue Balance', store=True)
    open_balance = fields.Monetary(compute='_credit_debit_get', string='Credit Open Balance', store=True)

    debit = fields.Monetary(store=True)     # Override to store
    credit = fields.Monetary(store=True)    # Override to store

    @api.depends('rec_pay_aml_ids', 'rec_pay_aml_ids.move_id.state', 'rec_pay_aml_ids.amount_residual',
                 'rec_pay_aml_ids.account_id.internal_type', 'rec_pay_aml_ids.date_maturity', 'rec_pay_aml_ids.date')
    @api.depends_context('force_company')
    def _credit_debit_get(self):
        """
        Inherit Odoo's to compute Total Overdue, Total Open Balance for both Customer and Vendor.
        Switch to store => need to specify dependent fields.
        """
        self.env['account.move'].flush(['state'])
        self.env['account.move.line'].flush()
        super(CustomerUSA, self.with_context(debit_credit=True))._credit_debit_get()

        self.overdue_amount = False
        self.open_balance = False
        self.debit_overdue_amount = False
        self.debit_open_balance = False

        tables, where_clause, where_params = self.env['account.move.line'].with_context(state='posted', company_id=self.env.company.id)._query_get()
        where_params = [tuple(self.ids)] + where_params
        where_clause = 'AND ' + where_clause if where_clause else ''

        query = """
            SELECT
                account_move_line.partner_id AS pid,
                act.type AS account_type,
                SUM(CASE WHEN account_move_line.date_maturity < CURRENT_DATE OR account_move_line.date_maturity IS NULL AND account_move_line.date < CURRENT_DATE 
                    THEN account_move_line.amount_residual ELSE 0 END) AS total_overdue,
                SUM(CASE WHEN account_move_line.date_maturity >= CURRENT_DATE OR account_move_line.date_maturity IS NULL AND account_move_line.date >= CURRENT_DATE
                    THEN account_move_line.amount_residual ELSE 0 END) AS total_open
            FROM {table}
                LEFT JOIN account_account a ON (account_move_line.account_id=a.id)
                LEFT JOIN account_account_type act ON (a.user_type_id=act.id)
            WHERE
                act.type IN ('receivable', 'payable') AND
                account_move_line.partner_id IN %s AND
                account_move_line.reconciled IS FALSE
                {where}
            GROUP BY pid, account_type
        """.format(table=tables, where=where_clause)

        self._cr.execute(query, where_params)
        data = self._cr.fetchall()

        for pid, account_type, total_overdue, total_open in data:
            partner = self.browse(pid)
            if account_type == 'receivable':
                partner.overdue_amount = total_overdue
                partner.open_balance = total_open
            elif account_type == 'payable':
                partner.debit_overdue_amount = -total_overdue
                partner.debit_open_balance = -total_open

    @api.onchange('print_check_as')
    def _onchange_print_check_as(self):
        for record in self:
            record.check_name = record.name

    @api.model
    def init_ref_value(self):
        for res_partner_record in self.env[RES_PARTNER].search([('ref', '=', None)], order='id'):
            res_partner_record.ref = self._get_ref_next_sequence()

    def _update_usa_partner_type(self):
        if self.ids:
            query = """
            UPDATE res_partner SET usa_partner_type =
                CASE
                    WHEN supplier_rank > 0 AND customer_rank > 0 THEN 'both'
                    WHEN supplier_rank > 0 AND customer_rank <= 0 THEN 'supplier'
                    WHEN supplier_rank <= 0 AND customer_rank > 0 THEN 'customer'
                    ELSE NULL
                END
            WHERE id IN %(partner_ids)s
            """
            self.env.cr.execute(query, {'partner_ids': tuple(self.ids)})

    def _increase_rank(self, field):
        super(CustomerUSA, self)._increase_rank(field)
        self._update_usa_partner_type()

    @api.model_create_multi
    def create(self, vals_list):
        res = super(CustomerUSA, self).create(vals_list)

        # Update usa_partner_type (Customer/Vendor/Both) after super()
        if vals_list and ('customer_rank' in vals_list[0] or 'supplier_rank' in vals_list[0]):
            res._update_usa_partner_type()

        return res

    def write(self, vals):
        res = super(CustomerUSA, self).write(vals)
        for partner in self:
            for child in partner.child_ids:
                child.ar_in_charge = partner.ar_in_charge
        return res
