# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

import random
import werkzeug.urls
import math

from odoo.tools import float_round


def random_token():
    # the token has an entropy of about 120 bits (6 bits/char * 20 chars)
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(random.SystemRandom().choice(chars) for _ in range(20))


def _get_url_from_menu(context, menu_external_id):
    base_url = context.env['ir.config_parameter'].get_param('web.base.url')
    menu_ref = context.env.ref(menu_external_id)
    action = menu_ref.action
    url = werkzeug.urls.url_join(base_url, "/web#action=%s&model=%s&view_type=%s&menu_id=%s" %
                                 (action.id, action.res_model, 'kanban', menu_ref.id,))
    return url


def get_margin_value(value, previous_value=0.0):
    margin = 0.0
    if (value != previous_value) and (value != 0.0 and previous_value != 0.0):
        margin = float_round((float(value-previous_value) / previous_value or 1) * 100, precision_digits=2)
    return margin


def format_currency_amount(amount, currency_id):
    pre = post = u''
    if currency_id.position == 'before':
        pre = u'{symbol}\N{NO-BREAK SPACE}'.format(symbol=currency_id.symbol or '')
    else:
        post = u'\N{NO-BREAK SPACE}{symbol}'.format(symbol=currency_id.symbol or '')
    return u'{pre}{0}{post}'.format(amount, pre=pre, post=post)


def is_equal(n1, n2):
    return math.isclose(n1, n2, abs_tol=1e-05)
