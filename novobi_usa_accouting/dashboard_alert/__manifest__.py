# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Dashboard Alert',
    'summary': '',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Accounting',
    'version': '1.0',
    'license': 'OPL-1',
    'depends': [
        'account_dashboard',
        'web'
    ],

    'data': [
        'security/ir.model.access.csv',
        'security/alert_info_security.xml',

        'data/inherited_kpi_journal_cron.xml',
        'data/personalized_alert_info_cron.xml',
        'data/kpi_alert_template_data.xml',
        'data/alert_channel_data.xml',
        'data/inherited_res_users_data.xml',

        'views/assets.xml',
        'views/alert_info_views.xml',
        'views/personalized_alert_info_views.xml',
        'views/alert_setting_templates.xml',
        'views/inherited_res_partner_views.xml',
        'views/inherited_res_users_views.xml',
        'views/inherited_res_config_setting_views.xml',

        'wizard/kpi_list_views.xml'
    ],
    'qweb': ['static/src/xml/*.xml'],
}
