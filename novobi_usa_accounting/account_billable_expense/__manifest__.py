{
    'name': 'Billable Expense - assigned to customer from Vendor Bill',
    'summary': 'Accounting: Billable Expense',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': [
        'l10n_generic_coa',
        'account_reports',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/billable_expense_report_data.xml',
        'data/mail_data.xml',
        'views/assets.xml',
        'views/account_move_view.xml',
        'views/billable_expense_view.xml',
        'views/billable_expense_report.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'images': ['static/description/main_screenshot.png'],
}
