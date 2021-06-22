# -*- coding: utf-8 -*-

import re
import locale
import base64
import datetime
import time
import odoo
from pytz import timezone
import dateutil

from odoo.tools import formatLang


def check_email_format(text):
    if re.match(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$", text):
        return True
    else:
        return False


def _get_the_first_and_the_last_truth_element(input_array, not_truth_element):
    """
    The function return the index of the first and the last truth element in `input_array`
    :param input_array:
    :param not_truth_element: is a list of value to compare with the value in `input_array` to know
    this element is truth value or not. It depends on your definition
    :return: index of the first and the last truth element
    """
    first_index = 0
    last_index = len(input_array) - 1
    while input_array[first_index] in not_truth_element or input_array[last_index] in not_truth_element:
        if input_array[first_index] in not_truth_element:
            first_index += 1
        if input_array[last_index] in not_truth_element:
            last_index -= 1
    return first_index, last_index


def format_currency(self, value):
    currency = self.env.user.company_id.currency_id
    return_value = formatLang(self.env, currency.round(value) + 0.0, currency_obj=currency)
    return return_value


def format_percentage(number):
    precision = 2
    str_num_formatted = "{:.{}f}".format(number, precision) + '%'
    return str_num_formatted


def get_list_companies_child(cur_coms):
    list_com_id = cur_coms.ids
    for com in cur_coms:
        for child in com.child_ids:
            list_com_id += get_list_companies_child(child)
    return list_com_id


def get_eval_context(self, model_name, user_id=None, company_id=None):
    """ Prepare the context used when evaluating python code, like the
    python formulas or code server actions.

    :param user_id:
    :param self:
    :param model_name:
    :param action: the current server action
    :type action: browse record
    :returns: dict -- evaluation context given to (safe_)safe_eval """
    if user_id:
        user = self.env['res.users'].search([('id', '=', user_id)])
    else:
        user_id = self._uid
        user = self.env.user

    eval_context = {
        'uid': user_id,
        'user': user,
        'time': time,
        'datetime': datetime,
        'dateutil': dateutil,
        'timezone': timezone,
        'b64encode': base64.b64encode,
        'b64decode': base64.b64decode,
    }
    model = self.env[model_name]
    if company_id:
        model._context.update({'company_id':company_id})
    record = None
    records = None
    if self._context.get('active_model') == model_name and self._context.get('active_id'):
        record = model.browse(self._context['active_id'])
    if self._context.get('active_model') == model_name and self._context.get('active_ids'):
        records = model.browse(self._context['active_ids'])
    if self._context.get('onchange_self'):
        record = self._context['onchange_self']
    eval_context.update({
        # orm
        'env': self.env,
        'model': model,
        # Exceptions
        'Warning': odoo.exceptions.Warning,
        # record
        'record': record,
        'records': records,
    })
    return eval_context


def format_human_readable_amount(amount, suffix=''):
    for unit in ['', 'K', 'M', 'G']:
        if abs(amount) < 1000.0:
            return "%3.2f%s%s" % (amount, unit, suffix)
        amount /= 1000.0
    return "%.2f%s%s" % (amount, 'T', suffix)


# def format_full_amount(amount, suffix=''):
#     amount_return = "%3.2f" % amount
#     i = 7
#     k = []
#     p = len(amount_return)
#     while i >= 2:
#         k.append(amount_return[i - 3: p])
#         print(i - 3, p - (i - 3))
#         i -= 3
#         p = i</div>
#     if i != 0:
#         k.append(amount_return[0:p])
#     k.reverse()
#     result = ','.join(k)
#     return result


def test(self, value):
    display_currency = self.env.user.company_id.currency_id
    fmt = "%.{0}f".format(display_currency.decimal_places)
    lang = self.env['res.lang']._lang_get(self.env.user.lang)
    formatted_value = lang.format(fmt, display_currency.round(value),
                                  grouping=True, monetary=True) \
        .replace(r' ', u'\N{NO-BREAK SPACE}').replace(r'-',
                                                      u'-\N{ZERO WIDTH NO-BREAK SPACE}')


def format_currency_amount(amount, currency_id, no_break_space=False):
    pre = post = u''
    if currency_id.position == 'before':
        pre = u'{symbol}%s'.format(symbol=currency_id.symbol or '') % \
               (u'\N{NO-BREAK SPACE}' if no_break_space else '', )
    else:
        post = u'%s{symbol}'.format(symbol=currency_id.symbol or '') % \
               (u'\N{NO-BREAK SPACE}' if no_break_space else '', )
    return u'{pre}{0}{post}'.format(amount, pre=pre, post=post)


def get_short_currency_amount(value, currency_id):
    converted_amount = format_human_readable_amount(value)
    short_title = format_currency_amount(converted_amount, currency_id)
    return short_title


def convert_value_with_unit_type(unit_type, raw_value, currency_id):
    """ Function convert raw_value to format defined in unit_type

    :param unit_type:
    :param raw_value:
    :param currency_id:
    :return:
    """
    if unit_type == 'currency':
        converted_amount = format_human_readable_amount(raw_value)
        value = format_currency_amount(converted_amount, currency_id)
    elif unit_type == 'percentage':
        value = format_percentage(raw_value)
    else:
        value = format_human_readable_amount(raw_value)
    return value
