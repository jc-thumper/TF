# -*- coding: utf-8 -*-
##############################################################################
#
#    Confianz IT
#    Copyright (C) 2020   (https://www.confianzit.com)
#
##############################################################################


{
    'name': "WorkCenter User Restriction",
    'version': '13.0.1.0',
    'category': 'MRP',
    'sequence': '15',
    'description': """
        This module will restrict the users so that individuals cannot complete
        work orders belonging to other work centers.
    """,
    'author': 'Confianz IT',
    'website': 'https://www.confianzit.com',
    'depends': ['mrp'],
    'data': [
        'views/work_center_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
