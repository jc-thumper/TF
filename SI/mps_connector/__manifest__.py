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
    'application': True,
    'post_init_hook': 'init_forecast_result_from_mps_data',
}
