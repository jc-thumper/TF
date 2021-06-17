{
    'name': 'TF Stock',
    'version': '1.0',
    'website': 'https://www.novobi.com',
    'category': '',
    'author': 'Novobi LLC',
    'depends': [
        'stock',
    ],
    'description': '',
    'data': [
        'report/product_category_report.xml',
        'report/component_usage_report_views.xml',
        'report/production_report_views.xml',

        'wizard/component_usage_wizard_views.xml',
        'wizard/production_report_wizard_views.xml',
    ],
    'images': [],
    'demo': [],
    'application': True,
    'installable': True,
    'auto_install': False,
    'qweb': ['static/src/xml/*.xml'],
}
