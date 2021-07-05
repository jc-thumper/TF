# -*- coding: utf-8 -*-

{
    'name': 'Billable Expense - assigned to customer from Purchase Order',
    'summary': 'Accounting: Billable Expense for Purchase',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'account_billable_expense',
    ],

    'data': [
        'views/purchase_order_view.xml',
        'report/search_template_view.xml',
        'report/billable_expense_report.xml',
    ],
    'images': ['static/description/main_screenshot.png'],
}
