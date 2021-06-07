# -*- coding: utf-8 -*-

{
    'name': 'SI: Stock Extend',
    'version': '3.0',
    'license': 'OPL-1',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Smart Inventory',
    'depends': [
        'stock'
    ],

    'data': [
        # ============================== VIEWS ================================
        'views/smart_inventory_views.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'application': False,
}
