# -*- coding: utf-8 -*-

{
    'name': 'Accounting Budget Advanced',
    'summary': 'Accounting Budget Advanced',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '1.0',
    'depends': [
        'account_accountant',
        'l10n_generic_coa',
        'account_budget',
        'account_reports',
    ],

    'data': [
        # 'data/account_data.xml',
        'data/account_financial_report_data.xml',

        'views/assets.xml',
        'views/account_financial_report_view.xml',
        'views/budget_entry_screen.xml',
        'views/budget_report_screen.xml',
        'views/account_budget_views.xml',
        'wizard/account_budget_wizard_view.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
}
