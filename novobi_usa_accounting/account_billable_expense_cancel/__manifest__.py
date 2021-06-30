{
    'name': 'Billable Expense - Cancel message',
    'summary': 'Accounting: Billable Expense - Cancel message',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': [
        'account_billable_expense',
        'l10n_us_accounting',
    ],
    'data': [
        'wizard/expense_invoice_to_draft_view.xml',
    ],
}
