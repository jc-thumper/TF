# -*- coding: utf-8 -*-

import logging
import re
import pytz

from datetime import datetime
from psycopg2.extensions import AsIs
from odoo.http import request

from odoo import _
from odoo.models import LOG_ACCESS_COLUMNS
from .datetime_utils import DEFAULT_DATETIME_FORMAT

_logger = logging.getLogger(__name__)

########################################################
# CONSTANTS
########################################################

REALTIME_VALUE = 'real_time'
TIME_INTERVAL_VALUE = 'time_interval'

TIME_OPTION_SELECTION = [(REALTIME_VALUE, _('Refresh On Dashboard Load')),
                         (TIME_INTERVAL_VALUE, _('Time Interval'))]

TIME_INTERVAL_SELECTION = [('minutes', _('minute(s)')),
                           ('hours', _('hour(s)')),
                           ('days', _('day(s)'))]

########################################################
# HELPER FUNCTION
########################################################


def query(cr, table_name, selected_fields, domain,
          order_by=None, limit=None, active_test=False, **kwargs):
    """
    Execute a sql query
    :param limit:
    :param active_test:
    :param order_by:
    :param cr:
    :param uid:
    :param table_name: str, the table of the model in Odoo
    For example: product.product, sale_order.line, ...
    :param selected_fields: str Ex: "barcode, active, product_tmpl_id"
    :param domain: list of tuple
    For example: [
        (<field_name>, <operator>, <value>),
        (<field_name>, <operator>, <value>),
        (<field_name>, <operator>, <value>)
    ]
    :return:
    :rtype: list[dict]
    """
    params = [AsIs(selected_fields)]

    sql_query = """select %s from %s"""

    # get the right table name in the database (without the dot notation)
    if table_name:
        params.append(AsIs(re.sub('\.', '_', table_name)))

    # parser domain
    if domain:
        where_domain = request.env[table_name]._where_calc(domain=domain, active_test=active_test)
        if where_domain:
            # get where condition
            sql_query += " where " + where_domain.get_sql()[1]
            # get params for where conditions
            params += where_domain.get_sql()[2]

    if 'group_by' in kwargs:
        sql_query += (" group by " + kwargs.get('group_by'))

    if order_by:
        sql_query += (" order by " + order_by)

    if limit:
        sql_query += " limit %s"
        params.append(limit)

    cr.execute(sql_query, params)
    _logger.info('query: %s', cr.mogrify(sql_query, params)[:500])
    records = cr.dictfetchall()
    return records


def dict_item_getter(*items):
    if len(items) == 1:
        item = items[0]
        def getf(dict_data):
            return dict_data.get(item, None)
    else:
        def getf(dict_data):
            return tuple(dict_data.get(item, None) for item in items)
    return getf


def get_query_params(insert_fields, json_data):
    """
    Return query params from ``json_data`` base on ``insert_fields``
    :param insert_fields:  a list of field name
    :param json_data: a dict
    :return:
    :rtype: list(dict)
    """
    return [list(dict_item_getter(*insert_fields)(item)) for item in json_data]


def generate_where_clause(field_names=[], values=[]):
    """
    Create where clause in sql query
    :param field_names: list of field used to compare the value in WHERE clause
    Ex: where product_id = %s and company_id is None and warehouse_id is None
    :param values: a list of value for each field in ``field_names``
    :return: a sql code and query param
    Ex:
    field_names = ['product_id', 'company_id', 'warehouse_id']
    values = [1, None, 1]
    sql_query = "product_id = %s and company_id is %s and warehouse_id = %s"
    query_params = [1, None, 1]
    """
    assert len(field_names) == len(values), "The length of field_names and values must be equal."
    sql_query = []
    query_params = []

    for field, value in zip(field_names, values):
        query_params.append(value)
        if value is None:
            operator = " is "
        else:
            operator = " = "

        sql_query.append(field + operator + "%s")

    sql_query_str = " AND ".join(sql_query)

    return sql_query_str, query_params


def get_db_cur_time(cr, timezone=None):
    """
    Get current time in the database
    :param cr: a cursor to the database
    :type cr: cursor
    :param timezone: the name of timezone in the library pytz without starting with 'Etc/'
    Ex: UTC, CST6CDT - Central Time, ...
    :type timezone: a string
    :return: datetime at specified timezone
    :rtype: datetime
    """
    sql_query = """SELECT now() as now;""" if timezone is None \
        else """SELECT (now() at time zone %s)::timestamp as now;"""
    sql_param = () if timezone is None else (timezone,)
    cr.execute(sql_query, sql_param)
    record = cr.dictfetchone()
    return record.get('now')


def get_all_timezone():
    """
    Return a list of timezone  with the short key and the description for this timezone
    :return:
    :rtype: a list of tuple
    [('UTC', 'UTC)]
    """
    _tzs = [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]
    return _tzs


def generate_domain_for_query(product_id=-1, company_id=-1, warehouse_id=-1, domain=None, **kwargs):
    """
    Generate the domain for the query in SQL
    :param product_id: int, the id of product
    If product_id = -1, it means we don't need to create a condition for this field
    If product_id is None, it means the value of this field is NULL in the database
    :param company_id: int, the id of company_id
    :param warehouse_id: int, the id of warehouse_id
    :param domain: list of tuple, another domain to append with the result returned by the function
    :param kwargs: we can add some fields to create a domain
    :return:
    """
    res = []
    if product_id and (product_id > 0):
        res.append(('product_id', '=', product_id))
    if company_id and (company_id > 0):
        res.append(('company_id', '=', company_id))
    if warehouse_id and (warehouse_id > 0):
        res.append(('warehouse_id', '=', warehouse_id))
    if type(domain) is list:
        res += domain

    return res


def append_log_access_fields_to_data(self, data, fields_to_append=None, current_time=None):
    """
    Add log access fields in the data
    :param self:
    :type data: dict
    :param fields_to_append: a list of column name to append
    :type fields_to_append: list(int)
    :param current_time: the current datetime at specify timezone or UTC
    :type current_time: datetime
    :return:
    """
    cur_time = current_time or get_db_cur_time(self.env.cr)
    if fields_to_append is None:
        fields_to_append = LOG_ACCESS_COLUMNS

    for log in fields_to_append:
        if log == 'create_uid':
            data['create_uid'] = self.env.ref("base.partner_root").id
        elif log == 'create_date':
            data['create_date'] = cur_time.strftime(DEFAULT_DATETIME_FORMAT)
        elif log == 'write_uid':
            data['write_uid'] = self.env.ref("base.partner_root").id
        elif log == 'write_date':
            data['write_date'] = cur_time.strftime(DEFAULT_DATETIME_FORMAT)

    return data
