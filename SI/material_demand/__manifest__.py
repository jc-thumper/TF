# -*- coding: utf-8 -*-

{
    'name': 'Material Demand',
    'summary': '',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': '',
    'version': '1.0',
    'depends': [
        'forecast_base', 'mrp_extend'
    ],

    'data': [
        'security/ir.model.access.csv',
    ],
    'qweb': ['static/src/xml/*.xml'],

    'application': False,
    'installable': True,
    'auto_install': True,
}
