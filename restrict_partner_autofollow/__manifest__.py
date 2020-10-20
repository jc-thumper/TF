# -*- encoding: utf-8 -*-
##############################################################################
#
#    Confianz IT
#    Copyright (C) 2020   (https://www.confianzit.com)
#
##############################################################################


{
    'name': "Restrict Partner Auto-Follow ",
    'version': '13.0.1.0',
    'category': 'mail',
    'sequence': '15',
    'description': "Auto follow restriction for partners",
    'author': 'Confianz IT',
    'website': 'https://www.confianzit.com',
    'depends': ['mail'],
    'data': [
        'wizard/follower_wizard_inherit.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
