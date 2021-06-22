# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi: Cash Flow Statement',
    'summary': 'Novobi: Cash Flow Statement',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '1.0',
    'license': 'OPL-1',
    'depends': [
        'account_reports',
    ],

    'data': [
        'security/ir.model.access.csv',

        'data/cash_flow_report_structure_data.xml',
        'data/advanced_cash_flow_report_data.xml',

        'views/assets.xml',
        'views/account_account_views.xml',
        'views/cash_flow_report_structure_views.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
}
