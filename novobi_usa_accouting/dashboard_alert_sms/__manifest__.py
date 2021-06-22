# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.
{
    'name': 'Account - SMS',
    'summary': '',
    'author': 'Novobi',
    'website': 'https://novobi.com',
    'category': 'Accounting',
    'version': '1.0',
    'license': 'OPL-1',
    'depends': [
        'dashboard_alert'
    ],

    'data': [
        'data/alert_channel_data.xml',

        'views/inherited_res_partner_views.xml',
        'views/inherited_res_config_setting_views.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
}
