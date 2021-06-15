# -*- coding: utf-8 -*-

{
    'name': 'SI: Engine Connector',
    'version': '3.0',
    'license': 'OPL-1',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Smart Inventory',
    'depends': [
        'si_core'
    ],

    'data': [
        # ============================== SECURITY =============================
        'security/ir.model.access.csv',
        # ============================== VIEWS ================================
        'data/register_service_scheduler.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'application': False,
}
