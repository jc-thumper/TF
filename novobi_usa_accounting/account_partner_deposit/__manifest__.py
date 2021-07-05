# -*- coding: utf-8 -*-

{
    'name': 'Accounting: Partner Deposit',
    'summary': 'Accounting: Partner Deposit',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '1.0',
    'depends': [
        'l10n_generic_coa',
        'account_reports',
        'account',
        'l10n_us_accounting',
    ],

    'data': [
        # 'security/ir.model.access.csv',
        'data/coa_chart_data.xml',

        'views/res_partner_view.xml',
        'views/account_payment_deposit_view.xml',
        'wizard/deposit_order_view.xml',
        'report/account_followup_report_templates.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
}
