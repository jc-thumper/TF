# -*- coding: utf-8 -*-

{
    'name': 'SI: Inventory Optimal Operation Base',
    'summary': """
    Smart Inventory: Inventory Optimal Operation Base 
    """,
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Smart Inventory',
    'version': '3.0',
    'license': 'OPL-1',
    'depends': [
        'inventory_optimization'
    ],

    'data': [
        # ============================== VIEWS ================================
        'views/optimal_operation_views.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'application': False,
    'installable': True,
    'auto_install': True,
}
