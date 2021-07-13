# -*- coding: utf-8 -*-

import logging
import os
import re
import psycopg2
import numpy as np

from operator import itemgetter

from .datetime_utils import check_datetime_format, FULL_DATETIME_FORMAT, DEFAULT_DATE_FORMAT, \
    DEFAULT_DATETIME_FORMAT
from .string_utils import check_password
from .response_message_utils import create_response_message, HTTP_400_BAD_REQUEST, HTTP_400_MSG, \
    HTTP_401_UNAUTHORIZED, HTTP_401_MSG, HTTP_200_OK, HTTP_200_MSG

_logger = logging.getLogger(__name__)

DOMAIN_SERVER_SI = os.environ.get('DOMAIN_SERVER_SI', 'https://smart-inventory.qa.novobi.com')


class ExtraFieldType:
    # CONSTANTS
    DATETIME_FIELD_TYPE = 'datetime'
    DATE_FIELD_TYPE = 'date'
    EMAIL_FIELD_TYPE = 'email'
    URL_FIELD_TYPE = 'URL'
    IP_ADDRESS_FIELD_TYPE = 'IP_address'

    LIST_FIELD_TYPES = [
        DATETIME_FIELD_TYPE,
        DATE_FIELD_TYPE,
        EMAIL_FIELD_TYPE,
        URL_FIELD_TYPE,
        IP_ADDRESS_FIELD_TYPE
    ]


class ServerAPICode:
    REGISTER = 'register'
    UPDATE_PROD_CONF = 'update_prod_fore_conf'
    UPDATE_CLSF_CONF = 'update_clsf_fore_conf'
    UPDATE_NEXT_TIME_RUN = 'update_next_time_run'
    UPDATE_PRODUCT_AGE = 'product_age_report'
    UPDATE_UNDER_OVERSTOCK_REPORT = 'under_overstock_report'
    CHECK_LICENSE_KEY = 'check_license_key'
    UPDATE_RRWF_REPORT = 'reordering_rules_with_forecast_report'


class ServerAPI:
    DICT_API_SUB_DOMAIN = {}

    @classmethod
    def get_api_url(cls, api_code):
        """ Function return the URL corresponding with `api_code`

        :param api_code:
        :type api_code: str
        :return: Return the URL of API, if not exist `api_code`,
        this will return empty string
        :rtype: str
        """
        return cls.DICT_API_SUB_DOMAIN.get(api_code, '')


class ServerAPIv1(ServerAPI):
    DICT_API_SUB_DOMAIN = {
        ServerAPICode.REGISTER: DOMAIN_SERVER_SI + '/api/register/',
        ServerAPICode.UPDATE_PROD_CONF: DOMAIN_SERVER_SI + '/api/update_prod_fore_conf/',
        ServerAPICode.UPDATE_CLSF_CONF: DOMAIN_SERVER_SI + '/api/update_clsf_fore_conf/',
        ServerAPICode.UPDATE_NEXT_TIME_RUN: DOMAIN_SERVER_SI + '/api/update_next_time_run/',
        ServerAPICode.UPDATE_PRODUCT_AGE: DOMAIN_SERVER_SI + '/api/product_age_report/',
        ServerAPICode.UPDATE_UNDER_OVERSTOCK_REPORT: DOMAIN_SERVER_SI + '/api/under_overstock_report/',
        ServerAPICode.CHECK_LICENSE_KEY: DOMAIN_SERVER_SI + '/api/check_license_key/',
        ServerAPICode.UPDATE_RRWF_REPORT: DOMAIN_SERVER_SI + '/api/reordering_rules_with_forecast_report/'
    }


def is_valid_field(data, field_name, field_type, required=True, extra_info=None):
    """

    :type   data: dict
    :param  field_name: the label of variable using to check in data variable
    :type   field_name: string
    :param  field_type: type of the corresponding value of the label
    :type   field_type: <class 'type'>
    :param  required:   is require field
    :type   required:   bool
    :param  extra_info: some constrain for special type of char field
    :type   extra_info: ExtraFieldType
    :return:    the check result of a valid field
    :rtype:     boolean
    """

    if required and field_name not in data.keys():
        key_error_msg = "The key '%s' is required." % field_name
        _logger.exception(key_error_msg, exc_info=True)
        raise KeyError(key_error_msg)

    field_value = data.get(field_name, None)
    regex = None

    if field_value is not None:
        if not isinstance(field_value, field_type) and not (field_type is float and isinstance(field_value, int)):
            type_error_msg = "The type of %s must be %s." % (field_name, field_type)
            _logger.exception(type_error_msg, exc_info=True)
            raise TypeError(type_error_msg)

        if extra_info is None:
            is_valid = True
        elif extra_info == ExtraFieldType.DATETIME_FIELD_TYPE:
            is_valid = check_datetime_format(field_value, DEFAULT_DATETIME_FORMAT, show_exception=False) or \
                       check_datetime_format(field_value, FULL_DATETIME_FORMAT, show_exception=False)
        elif extra_info == ExtraFieldType.DATE_FIELD_TYPE:
            is_valid = check_datetime_format(field_value, DEFAULT_DATE_FORMAT, show_exception=False)
        else:
            if extra_info == ExtraFieldType.EMAIL_FIELD_TYPE:
                # Email address regex
                regex = r'([\w\.\-\_]+)?\w+@[\w\-\_]+(\.\w+){1,}'
            elif extra_info == ExtraFieldType.URL_FIELD_TYPE:
                # URL regex
                regex = r'([\--\:\w?\[@%&+~#=]]*\.[a-z]{2,4}\/{0,2})((?:[?&](?:\w+)=(?:\w+))+|[--:\w?@%&+~#=]+)?'
            elif extra_info == ExtraFieldType.IP_ADDRESS_FIELD_TYPE:
                # IPv4 address regex
                regex = r'(?:(?:2(?:[0-4][0-9]|5[0-5])|[0-1]?[0-9]?[0-9])\.){3}(?:(?:2([0-4][0-9]|5[0-5])|[0-1]?[' \
                        r'0-9]?[0-9])) '

            pattern = re.compile(regex)
            # result is a matched object if the string is whole matched with the pattern, otherwise result is None
            result = re.fullmatch(pattern, field_value)
            is_valid = False if result is None else True
    else:
        # the value of this field can be None
        is_valid = True

    return is_valid


def check_json_fields(json_data, infos_required_field, infos_non_required_field):
    """ Check required keyword in json data and the type of each field

    :type   json_data: dict
    :param  infos_required_field: list of required fields and type of it
    :type   infos_required_field: list((<field_name>, <field_type>, <extra_info>), ...)
    <extra_info> can be datetime/email/URL/IPAddress
    :param  infos_non_required_field: list of required fields and type of it
    :type   infos_non_required_field: list((<field_name>, <field_type>, <extra_info>), ...)
    :return:
    """
    try:
        for field_name, field_type, extra_info in infos_required_field:
            is_valid_field(json_data, field_name, field_type, required=True, extra_info=extra_info)

        for field_name, field_type, extra_info in infos_non_required_field:
            is_valid_field(json_data, field_name, field_type, required=False, extra_info=extra_info)

        return True

    except KeyError as key_error:
        _logger.exception("There was an KeyError when checking json fields.")
        raise key_error

    except TypeError as type_error:
        _logger.exception("There was an TypeError when checking json fields.")
        raise type_error


def check_request_authentication(context, json_data):
    """

    :param context:
    :param json_data: dict
    :return:
    """
    # check server password
    server_password = json_data.get('server_pass')
    is_auth = context.env['forecasting.config.settings'].check_si_pass(context, server_password)
    from odoo.tools import config
    forecasting_test = config.get("forecasting_test", False)
    return forecasting_test or is_auth


def check_format_crawl_data_request(json_data, non_required_fields_and_types=None):
    """
    Check format the body of HTTP request in Client API
    For example:
    data = {
        'num_item': <int>,
        'time_to': <YYYY-mm-dd HH:MM:SS>,
        'password': <str>,
        'last_write_time': <YYYY-mm-dd HH:MM:SS>,
        'last_id': <int>}
    :param json_data: dict object
    :param non_required_fields_and_types: list of fields are not required and type of it
    :type non_required_fields_and_types: list((<field_name>, <field_type>, None), ...)
    :return: True if valid, otherwise raise Error
    """
    try:
        check_json_fields(json_data,
                          infos_required_field=[('num_item', int, None),
                                                ('time_to', str, ExtraFieldType.DATETIME_FIELD_TYPE),
                                                ('password', str, None),
                                                ('last_id', int, None)],
                          infos_non_required_field=non_required_fields_and_types)

        return True

    except KeyError as key_error:
        _logger.exception("Missing fields in body's request.", exc_info=True)
        raise key_error

    except TypeError as type_error:
        _logger.exception("Invalid type in in body's request.", exc_info=True)
        raise type_error

    except ValueError as value_error:
        _logger.exception("Vale error in in body's request.", exc_info=True)
        raise value_error


def check_format_data_array(data_field, required_fields_for_data, infos_non_required_field=None):
    """
    Check format of the card data in body of HTTP request in API update
    classification

    :param infos_non_required_field:
    :param required_fields_for_data:
    :param data_field: list dicts
    :return: True if valid, otherwise raise Error
    """
    infos_non_required_field = infos_non_required_field or []
    try:
        is_valid_format = True
        idx = 0
        size_data = len(data_field)
        while is_valid_format and idx < size_data:
            ith_item = data_field[idx]
            is_valid_format = check_json_fields(
                ith_item,
                infos_required_field=required_fields_for_data,
                infos_non_required_field=infos_non_required_field)
            idx += 1

    except Exception as e:
        _logger.exception("There was an error when checking format data array.")
        raise e

    return is_valid_format


def is_authentication(raw_password, hashed_password):
    return check_password(raw_password, hashed_password)


def generate_domain_for_crawl_data_query(data):
    domain = [('write_date', '<', data.get('time_to'))]

    if 'last_write_time' in data:
        domain.append(('write_date', '>', data.get('last_write_time')))
        domain = ['|', '&', ('id', '>', data.get('last_id')), ('write_date', '=', data.get('last_write_time')),
                  '&'] + domain

    return domain


def get_key_value_in_dict(dict_value, keys):
    """
    Return value in a dictionary base on the order of key in ``keys``
    :param dict_value:
    :type dict_value: dict
    :param keys: a list of key to get the data
    :type keys: list
    :return:
    :rtype: list
    """
    result = []
    try:
        if len(keys) == 1:
            result = [itemgetter(*list(keys))(dict_value)]
        elif len(keys) > 1:
            result = list(itemgetter(*list(keys))(dict_value))

    except Exception as e:
        _logger.exception("There was an error when get key value from dictionary.")
        raise e

    return result


def check_format_json_request(env, model, json_data, forecast_level, **kwargs):
    """
    Check format of the body of HTTP request in API update product classification

    :param json_data: dict object
    :return: True if valid, otherwise raise Error
    """
    try:
        is_valid_format = check_json_fields(
            json_data,
            infos_required_field=[('server_pass', str, None),
                                  ('data', list, None)],
            infos_non_required_field=[])

        # check the format of ``data`` fields
        list_data = json_data.get('data', [])

        if is_valid_format:
            required_fields_for_data = model.get_json_required_fields(forecast_level=forecast_level)
            non_required_fields_for_data = []
            is_valid_format = check_format_data_array(
                list_data,
                required_fields_for_data=required_fields_for_data,
                infos_non_required_field=non_required_fields_for_data
            )
        return is_valid_format

    except KeyError as key_error:
        _logger.exception("There was an KeyError when checking json request format.")
        raise key_error

    except TypeError as type_error:
        _logger.exception("There was an TypeError when checking json request format.")
        raise type_error

    except ValueError as value_error:
        _logger.exception("There was an ValueError when checking json request format.")
        raise value_error


def handle_push_data_request(request, model):
    """

    :param Request request: request data
    :param model: object model
    :return:
    """
    try:
        data = request.jsonrequest

        # Step 1: check if the request is authorized or not
        authorized_request = check_request_authentication(context=request, json_data=data)
        assert authorized_request, "Unauthorized"

        # get company_id from JSON data
        list_data = data.get('data', [])
        company_ids = np.unique([item.get('company_id') for item in list_data]).tolist()
        forecast_level_by_companies = request.env['res.company'].sudo().get_forecast_level_by_company(
            company_ids=company_ids)

        for company_id, forecast_level in forecast_level_by_companies.items():
            filtered_data = list(filter(lambda row: row.get('company_id') == company_id, list_data))

            # Step 2: check format of data in request
            required_fields_for_data = model.get_json_required_fields(forecast_level=forecast_level)
            non_required_fields_for_data = []
            is_valid = check_format_data_array(filtered_data,
                                               required_fields_for_data=required_fields_for_data,
                                               infos_non_required_field=non_required_fields_for_data)

            # if the returned data don't have any item to update, we will not need to run this logic
            if is_valid:
                if len(filtered_data):
                    # Step 3: transform data in request
                    parsed_data = model.transform_json_data_request(list_data=filtered_data)

                    # get time when records are created in the database
                    created_date = parsed_data[0].get('create_date')

                    # Step 4: update data to the table
                    model.create_or_update_records(vals=parsed_data, forecast_level=forecast_level)

                    # Step 5: push next actions into queue jobs if it is existing
                    if hasattr(model, 'trigger_next_actions'):
                        model.trigger_next_actions(**{
                            'created_date': created_date,
                            'forecast_level': forecast_level,
                            'company_id': company_id
                        })
            else:
                _logger.warning('The format of data used to import to %s is the wrong format', model.name)

        # Step 6: create the response
        response_message = create_response_message(success=True, code=HTTP_200_OK, res_msg=HTTP_200_MSG,
                                                   data={})
    except KeyError as key_error:
        _logger.exception('Key Error when handle the request', exc_info=True)
        response_message = create_response_message(success=False, code=HTTP_400_BAD_REQUEST, res_msg=HTTP_400_MSG,
                                                   detail=str(key_error))
    except TypeError as type_error:
        _logger.exception('Type Error when handle the request', exc_info=True)
        response_message = create_response_message(success=False, code=HTTP_400_BAD_REQUEST, res_msg=HTTP_400_MSG,
                                                   detail=str(type_error))
    except ValueError as value_error:
        _logger.exception('Value Error when handle the request', exc_info=True)
        response_message = create_response_message(success=False, code=HTTP_400_BAD_REQUEST, res_msg=HTTP_400_MSG,
                                                   detail=str(value_error))
    except AssertionError:
        _logger.exception('Unauthorized request', exc_info=True)
        response_message = create_response_message(success=False, code=HTTP_401_UNAUTHORIZED,
                                                   res_msg=HTTP_401_MSG)
    except (psycopg2.DatabaseError, Exception) as db_error:
        _logger.exception('Error while fetching data from database', exc_info=True)
        response_message = create_response_message(success=False, code=HTTP_400_BAD_REQUEST, res_msg=HTTP_400_MSG,
                                                   detail=str(db_error))
    return response_message
