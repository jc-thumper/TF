# -*- encoding: utf-8 -*-
##############################################################################
#
#    Confianz IT
#    Copyright (C) 2020   (https://www.confianzit.com)
#
##############################################################################


{
    'name': "MRP Placeholder Product Warning",
    'version': '13.0.1.0',
    'category': 'MRP',
    'sequence': '15',
    'description': "This module will show Placeholder Product Warning on MO Todo action",
    'author': 'Confianz IT',
    'website': 'https://www.confianzit.com',
    'depends': ['mrp'],
    'data': [
        'views/mrp_production_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
