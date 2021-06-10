# -*- coding: utf-8 -*-

{
    'name': 'SI: MPS Connector',
    'version': '3.0',
    'license': 'OPL-1',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Smart Inventory',
    'depends': [
        'mrp_mps', 'forecast_base'
    ],

    'data': [
        # ============================== VIEWS ================================
    ],
    'qweb': ['static/src/xml/*.xml'],
    'application': False,
    'post_init_hook': 'setup_mps_connector',
}
