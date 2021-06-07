# -*- coding: utf-8 -*-

{
    'name': 'SI: Smart Inventory Library',
    'summary': '',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Smart Inventory',
    'version': '3.0',
    'license': 'OPL-1',
    'depends': [
        'base', 'web', 'product', 'stock_extend', 'queue_job'
    ],

    'data': [
        # ============================== DATA ===============================
        'data/ir_module_category_data.xml',

        # ============================== VIEWS ===============================
        'views/assets.xml',
        'views/onboarding_views.xml',
        'views/inherit_stock_warehouse_tree_view.xml',

        # ============================== WIZARDS ===============================
        'wizard/wizard_confirm_box_view.xml',
        'wizard/wizard_warning_box_view.xml'
    ],

    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,
    'price': 0,
	'currency': 'USD',
	'support': 'support@novobi.com',
}
