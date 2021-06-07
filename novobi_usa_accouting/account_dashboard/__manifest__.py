# -*- coding: utf-8 -*-
{
    'name': "Account Dashboard",

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

    # any module necessary for this one to work correctly
    'depends': [
        'l10n_us_accounting', 'l10n_custom_dashboard'
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/personalized_kpi_info_security.xml',
        'security/account_dashboard_security.xml',
        # 'security/digest_security.xml',

        'data/usa_journal_data.xml',
        'data/kpi_journal_data.xml',
        'data/digest_data.xml',
        'data/inherited_digest_template_data.xml',
        'data/account_journal_data.xml',

        'views/assets.xml',
        'views/account_dashboard_views.xml',
        'views/kpi_dashboard_views.xml',
        'views/personalized_kpi_info_views.xml',
        'views/inherited_account_journal_dashboard_views.xml',
        'views/digest_views.xml',

        # 'wizards/confirm_message_views.xml',

        #'data/usa_journal_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
}
