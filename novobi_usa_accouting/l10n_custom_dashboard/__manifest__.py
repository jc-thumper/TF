# -*- coding: utf-8 -*-
{
    'name': "Custom Dashboard",
    'summary': """""",
    'description': """
    """,
    'author': 'Novobi',
    'website': 'https://novobi.com',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '1.0',

    'depends': [
        'base'
    ],

    'data': [
        'views/assets.xml',
    ],
    'demo': [],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
}
