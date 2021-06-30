# -*- coding: utf-8 -*-

{
    'name': 'Accounting: Partner Deposit for Purchase Order',
    'summary': 'Accounting: Partner Deposit for Purchase Order',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '1.0',
    'depends': [
        'account_partner_deposit',
        'purchase',
    ],

    'data': [
        # 'security/ir.model.access.csv',

        'views/purchase_order_view.xml',
        'views/account_payment_view.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
}
