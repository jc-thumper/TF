{
    "name": "Base Marketplace Connector",
    "version": "13.0.1.1",
    "category": "Extra",
    "summary": "Base app for all the marketplace apps.",

    "depends": ['account', 'delivery'],

    'data': [
        'security/group.xml',
        'security/ir.model.access.csv',

        'report/marketplace_sale_report_views.xml',

        'wizards/operation_view.xml',

        'views/marketplace_listing_item_view.xml',
        'views/marketplace_listing_view.xml',
        'views/product_view.xml',
        'views/marketplace_listing_image_view.xml',
        'views/sale_view.xml',
        'views/pricelist_view.xml',
        'views/account_move_view.xml',
        'views/stock_view.xml',
        'views/log_view.xml',
        'views/res_partner.xml',

        'data/ir_sequence_data.xml',
        'data/ir_cron.xml',
        'data/dashboard_data.xml',

        'views/marketplace_queue_job_line_view.xml',
        'views/marketplace_queue_job_view.xml',
        'views/marketplace_instance_view.xml',
        'views/marketplace_templates.xml',
        'views/marketplace_menuitems.xml',

    ],

    'images': ['static/description/base_marketplace.jpg'],

    'qweb': [
        'static/src/xml/systray.xml',
        'static/src/xml/dashboard.backend.xml',
    ],

    "author": "Teqstars",
    "website": "https://teqstars.com",
    'support': 'support@teqstars.com',
    'maintainer': 'Teqstars',

    "description": """
        """,

    'demo': [],
    'license': 'OPL-1',
    'live_test_url': '',
    'auto_install': False,
    'installable': True,
    'application': False,
    "price": "70.00",
    "currency": "EUR",
}
