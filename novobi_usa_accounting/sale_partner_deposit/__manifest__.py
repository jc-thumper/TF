# -*- coding: utf-8 -*-

{
    'name': 'Accounting: Partner Deposit for Sales Order',
    'summary': 'Accounting: Partner Deposit for Sales Order',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '1.0',
    'depends': [
        'account_partner_deposit',
        'sale_management',
    ],

    'data': [
        # 'security/ir.model.access.csv',

        'wizard/sale_make_invoice_advance_view.xml',

        'views/sale_order_view.xml',
        'views/account_payment_view.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
}
