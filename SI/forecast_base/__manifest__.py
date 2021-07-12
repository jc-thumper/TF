# -*- coding: utf-8 -*-

{
    'name': 'SI: Forecast Base',
    'summary': '',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Smart Inventory',
    'version': '3.0',
    'license': 'OPL-1',
    'depends': [
        'si_core',
    ],

    'data': [
        'security/product_classification_info_security.xml',
        'security/forecast_result_adjust_security.xml',
        'security/forecast_result_adjust_line_security.xml',
        'security/forecast_security.xml',
        'security/ir.model.access.csv',

        'data/product_classification_info_data.xml',
        'data/demand_classification_result_data.xml',
        'data/service_level_result_data.xml',
        'data/demand_classification_data.xml',
        'data/forecast_group_data.xml',
        'data/forecast_level_strategy_data.xml',
        'data/service_level_data.xml',
        'data/forecast_result_data.xml',
        'data/summarize_rec_result_data.xml',
        'data/res_company_data.xml',
        'data/ir_cron_data.xml',

        'views/inherit_res_config_settings_view.xml',
        'views/forecast_group_views.xml',
        'views/company_views.xml',
        'views/product_views.xml',
        'views/demand_type_views.xml',
        'views/service_level_views.xml',
        'views/demand_forecast_tree_view.xml',

        'wizard/license_confirm_box_view.xml',
        'wizard/license_warning_box_view.xml'
    ],

    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,

    "post_init_hook": "post_init_hook",
}
