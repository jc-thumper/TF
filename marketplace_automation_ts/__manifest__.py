{
    "name": "Marketplace Automation",
    "version": "13.0.0.4",
    "category": "Extra",
    "summary": "Base app for Marketplace Apps. Perform automation stuff for sale orders and Invoices.",

    "depends": ['account', 'stock', 'sale_management'],

    'data': [
        'security/ir.model.access.csv',

        'views/order_workflow_view.xml',
        'views/sale_view.xml',

    ],

    'images': ['static/description/slideshow/mk_automation.gif'],

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
    'qweb': [],
    "price": "30.00",
    "currency": "EUR",
}
