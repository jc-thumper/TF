# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2019 EquickERP
#
##############################################################################

{
    'name' : 'Merge Duplicate Data',
    'category': 'Extra Tools',
    'version': '13.0.1.0',
    'author': 'Equick ERP',
    'description': """
        This Module allows to merge duplicate data.
        * Allows you to merge the duplicate data.
        * User can merge the duplicate data of any model like Product, Partners, Product Category as well as any Custom model.
        * It will update the duplicate record reference with original record at all places in your odoo system.
        * It gives the option for what action you want to perform on the duplicate record like Delete, Archived or Nothing.
    """,
    'summary': """merge sale order | merge purchase order | remove duplicate data | merge customer | delete duplicate product | merge duplicate data | remove duplicate product | remove duplicate customer |remove|delete|data clean | duplicate|merge | merge data""",
    'depends' : ['base'],
    'price': 49,
    'currency': 'EUR',
    'license': 'OPL-1',
    'website': "",
    'data': [
        'security/ir.model.access.csv',
        'wizard/wizard_merge_data_view.xml',
    ],
    'demo': [],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: