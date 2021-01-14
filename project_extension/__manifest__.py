# -*- coding: utf-8 -*-

{
    "name": "Project Extension",
    "version": "1.1",
    "category": 'Project Management',
    'complexity': "normal",
    'author': 'Confianz Global,Inc.',
    'description': """
Project Extension   """,
    'website': 'http://www.confianzit.com',

    "depends": ['base', 'project'],

    'data': [
        'views/project_stage_view.xml',
        'views/project_view.xml',
             ],
    'demo_xml': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
