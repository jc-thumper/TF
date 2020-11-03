# -*- encoding: utf-8 -*-
##############################################################################
#
#    Confianz IT
#    Copyright (C) 2020   (https://www.confianzit.com)
#
##############################################################################


{
    'name': "Many2One No-Create",
    'version': '13.0.1.0',
    'category': 'web',
    'sequence': '15',
    'description': """
        This module will hide `Create` and `Create & Edit` options from many2one drop down.
    """,
    'author': 'Confianz IT',
    'website': 'https://www.confianzit.com',
    'depends': ['web'],
    'data': [
        'views/assets.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
