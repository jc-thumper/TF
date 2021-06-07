# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    customer_deposit_journal_id = fields.Many2one('account.journal', string="Customer Deposit Journal")
    vendor_deposit_journal_id = fields.Many2one('account.journal', string="Vendor Deposit Journal")

    @api.model
    def create_new_accounting_data(self):
        """
        This function runs when we first install the module: create accounting data for existing companies.
        :return:
        """
        superself = self.sudo()
        all_companies = superself.search([])

        for company in all_companies:
            if company.chart_template_id:
                # Journal
                superself.check_create_journal(company, 'general', 'Customer Deposit', 'CDEP',
                                               'customer_deposit_journal_id')
                superself.check_create_journal(company, 'general', 'Vendor Deposit', 'VDEP',
                                               'vendor_deposit_journal_id')

                # Account
                if company.chart_template_id == self.env.ref('l10n_generic_coa.configurable_chart_template'):
                    prepayment = superself.check_create_account('103000', 'Prepayments',
                                                   self.env.ref('account.data_account_type_prepayments'), company)
                    deposit = superself.check_create_account('111400', 'Customer Deposit',
                                                   self.env.ref('account.data_account_type_current_liabilities'), company)

                    # Property
                    company.check_create_property('property_account_customer_deposit_id', deposit)
                    company.check_create_property('property_account_vendor_deposit_id', prepayment)

    @api.model
    def check_create_account(self, code, name, user_type, company):
        Account = self.env['account.account']
        account_id = Account.search([('code', '=', code), ('name', 'like', name),
                                     ('user_type_id', '=', user_type.id), ('company_id', '=', company.id)], limit=1)
        if not account_id:
            account_id = Account.create({'code': code,
                                         'name': name,
                                         'user_type_id': user_type.id,
                                         'reconcile': True,
                                         'company_id': company.id})
        else:
            if not account_id.reconcile:
                account_id.reconcile = True

        return account_id

    @api.model
    def check_create_journal(self, company, type, name, code, field):
        Journal = self.env['account.journal']
        journal_id = Journal.search([('company_id', '=', company.id),
                                     ('type', '=', type), ('code', '=', code)])

        if journal_id:
            company[field] = journal_id
        else:
            company[field] = Journal.create({
                'type': type,
                'name': _(name),
                'code': code,
                'company_id': company.id,
                'show_on_dashboard': False,
            })

    def check_create_property(self, field_name, account):
        PropertyObj = self.env['ir.property']
        ModelFields = self.env['ir.model.fields']
        value = account and 'account.account,' + str(account.id) or False
        if value:
            field = ModelFields.search([('name', '=', field_name),
                                        ('model', '=', 'res.partner'),
                                        ('relation', '=', 'account.account')], limit=1)
            vals = {
                'name': field_name,
                'company_id': self.id,
                'fields_id': field.id,
                'value': value,
            }
            properties = PropertyObj.search([
                ('name', '=', field_name),
                ('fields_id', '=', field.id),
                ('res_id', '=', ''),
                ('company_id', '=', self.id),
            ])
            if properties:
                properties.write(vals)
            else:
                # create the property
                PropertyObj.create(vals)
