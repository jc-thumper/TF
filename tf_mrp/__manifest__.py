{
    'name': 'TF Manufacturing',
    'version': '1.0',
    'website': 'https://www.novobi.com',
    'category': '',
    'author': 'Novobi LLC',
    'depends': [
        'stock',
        'mrp',
    ],
    'description': '',
    'data': [
        'security/ir.model.access.csv',

        'views/stock_warehouse_orderpoint_views.xml',

        'wizard/sync_reordering_rule_to_mps_views.xml',
    ],
    'images': [],
    'demo': [],
    'application': False,
    'installable': True,
    'auto_install': False,
    'qweb': ['static/src/xml/*.xml'],
}
