# -*- coding: utf-8 -*-

{
    'name': 'SI: Reordering Rules with Forecast',
    'summary': """
    Smart Inventory: Recommend the Reordering Rules using the product future demand
    """,
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Smart Inventory',
    'version': '3.0',
    'license': 'OPL-1',
    'depends': [
        'inventory_optimal_operation'
    ],

    'data': [
        # ============================== SECURITY =================================
        'security/ir.model.access.csv',

        # ============================== DATA ================================
        'data/reordering_rules_with_forecast_data.xml',
        'data/ir_cron_data.xml',

        # ============================== VIEWS ================================
        'views/inherit_res_config_settings_view.xml',
        'views/reordering_rules_with_forecast_view.xml',

        # ============================== WIZARD ================================
        'wizard/ignore_apply_zero_max_qty_views.xml',
        'wizard/wizard_rrwf_confirm_box_views.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'post_init_hook': 'init_reordering_rules_with_forecast',
    'auto_install': True,
}
