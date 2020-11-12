# -*- encoding: utf-8 -*-
##############################################################################
#
#    Confianz IT
#    Copyright (C) 2020   (https://www.confianzit.com)
#
##############################################################################


{
    'name': "Stripe Payment Extension",
    'version': '13.0.1.0',
    'category': 'Accounting',
    'sequence': '15',
    'description': "Stripe Payment Button & Stripe Payment Auto Reconciliation",
    'author': 'Confianz IT',
    'website': 'https://www.confianzit.com',
    'depends': ['account', 'payment_stripe'],
    'data': [
        'views/account_move_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
