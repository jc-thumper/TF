# -*- coding: utf-8 -*-

{
    'name': 'SI: MRP Extend',
    'version': '3.0',
    'license': 'OPL-1',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Smart Inventory',
    'depends': [
        'mrp', 'stock_extend'
    ],

    'data': [
        # ============================== SECURITIES ================================
        'security/ir.model.access.csv',

        # ============================== DATA ================================
        'data/ir_cron_data.xml',

        # ============================== DATA ================================
        'views/inherit_product_product_views.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'application': False,
}
