# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    property_account_customer_deposit_id = fields.Many2one('account.account.template',
                                                            string="Customer Deposit Account")
    property_account_vendor_deposit_id = fields.Many2one('account.account.template',
                                                             string="Vendor Deposit Account")
    #####
    ## These functions run when we install a new chart template 
    #####
    def _prepare_all_journals(self, acc_template_ref, company, journals_dict=None):
        res = super(AccountChartTemplate, self)._prepare_all_journals(
            acc_template_ref, company, journals_dict=journals_dict)

        res += [{'type': 'general', 'name': _('Customer Deposit'), 'code': 'CDEP',
                 'company_id': company.id, 'show_on_dashboard': False},
                {'type': 'general', 'name': _('Vendor Deposit'), 'code': 'VDEP',
                 'company_id': company.id, 'show_on_dashboard': False}]
        return res

    @api.model
    def generate_journals(self, acc_template_ref, company, journals_dict=None):
        res = super(AccountChartTemplate, self).generate_journals(acc_template_ref, company, journals_dict=journals_dict)

        customer_deposit_journal_id = self.env['account.journal'].search([('company_id', '=', company.id),
                                                                          ('type', '=', 'general'),
                                                                          ('code', '=', 'CDEP')])
        if customer_deposit_journal_id:
            company.customer_deposit_journal_id = customer_deposit_journal_id

        vendor_deposit_journal_id = self.env['account.journal'].search([('company_id', '=', company.id),
                                                                        ('type', '=', 'general'),
                                                                        ('code', '=', 'VDEP')])
        if vendor_deposit_journal_id:
            company.vendor_deposit_journal_id = vendor_deposit_journal_id

        return res

    def generate_properties(self, acc_template_ref, company):
        res = super().generate_properties(acc_template_ref=acc_template_ref, company=company)
        PropertyObj = self.env['ir.property']
        todo_list = [
            ('property_account_customer_deposit_id', 'res.partner', 'account.account'),
            ('property_account_vendor_deposit_id', 'res.partner', 'account.account'),
        ]
        for record in todo_list:
            account = getattr(self, record[0])
            value = account and 'account.account,' + str(acc_template_ref[account.id]) or False
            if value:
                field = self.env['ir.model.fields'].search([('name', '=', record[0]), ('model', '=', record[1]), ('relation', '=', record[2])], limit=1)
                vals = {
                    'name': record[0],
                    'company_id': company.id,
                    'fields_id': field.id,
                    'value': value,
                }
                properties = PropertyObj.search([('name', '=', record[0]),
                                                 ('fields_id', '=', field.id),
                                                 ('res_id', '=', ''),
                                                 ('company_id', '=', company.id)])
                if properties:
                    #the property exist: modify it
                    properties.write(vals)
                else:
                    #create the property
                    PropertyObj.create(vals)
        return res
