{
    'name': 'Novobi: Stock Valuation Improvement',
    'summary': 'Novobi: Stock Valuation Improvement',
    'author': 'Novobi',
    'website': 'https://www.novobi.com/',
    'depends': [
        'base',
        'stock_account',
    ],
    'data': [
        'security/ir.model.access.csv',

        'views/stock_account_views.xml',
    ],
    'application': False,
    'installable': True,
}
