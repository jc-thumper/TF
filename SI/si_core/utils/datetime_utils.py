# -*- coding: utf-8 -*-

import calendar
import logging
from collections import OrderedDict

from datetime import datetime, timedelta, date
from typing import List

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, WEEKLY, MONTHLY, YEARLY

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from .string_utils import PeriodType

_logger = logging.getLogger(__name__)

######################################
# CONSTANTS
######################################
FULL_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_TIMEZONE = 'US/Central'
US_DATETIME_FORMAT = '%m/%d/%y %H:%M:%S'


######################################
# HELPER FUNCTION
######################################

def check_datetime_format(datetime_str, dt_format=DEFAULT_DATETIME_FORMAT, show_exception=False):
    """

    :param datetime_str
    :param dt_format
    :param show_exception
    """
    try:
        datetime.strptime(datetime_str, dt_format)
        return True
    except ValueError:
        expectation_msg = "Incorrect datetime format: %s, the format should be: %s " % (datetime_str, dt_format)
        if show_exception is True:
            _logger.exception(expectation_msg, exc_info=True)
            raise ValueError(expectation_msg)
    return False


def get_start_end_date_value(date_value, period_type):
    """
        Get the start date_value and end date_value from datetime value follow with forecasting_type
        and return couple of value start_date_value and end_date_value
        type DateTime of date_value follow by period_type

    :param datetime date_value:
    :param str period_type:
    :return: start date and end date of the period
    :rtype: (datetime, datetime)
    """
    start_date_value = None
    end_date_value = None
    if date_value and period_type:
        if period_type == PeriodType.DAILY_TYPE:
            start_date_value = date_value.replace(minute=0, hour=0, second=0, microsecond=0)
            end_date_value = start_date_value
        elif period_type == PeriodType.WEEKLY_TYPE:
            # get Monday of (week, year)
            date_delta = date_value.isoweekday()
            start_date_value = date_value - timedelta(days=(date_delta - 1))
            end_date_value = date_value + timedelta(days=(7 - date_delta))
        elif period_type == PeriodType.MONTHLY_TYPE:
            start_date_value = datetime(date_value.year, date_value.month, 1)
            end_date_value = datetime(date_value.year, date_value.month,
                                      calendar.monthrange(date_value.year, date_value.month)[1])
        elif period_type == PeriodType.QUARTERLY_TYPE:
            month = int((date_value.month - 1) / 3) * 3 + 1
            start_date_value = datetime(date_value.year, month, 1)

            end_date_value = datetime(date_value.year, month + 2,
                                      calendar.monthrange(date_value.year, month + 2)[1])
        elif period_type == PeriodType.YEARLY_TYPE:
            start_date_value = datetime(date_value.year, 1, 1)
            end_date_value = datetime(date_value.year, 12, 31)

    return start_date_value, end_date_value


def get_delta_time(period_type, no_periods=1):
    """
        Return the delta time base on period type

    :param no_periods:
    :param period_type:
    :return: relativedelta
    :rtype: int
    """
    delta_time = relativedelta(days=0)
    if period_type == PeriodType.DAILY_TYPE:
        delta_time = relativedelta(days=no_periods)
    elif period_type == PeriodType.WEEKLY_TYPE:
        delta_time = relativedelta(days=7 * no_periods)
    elif period_type == PeriodType.BIWEEKLY:
        delta_time = relativedelta(days=14 * no_periods)
    elif period_type == PeriodType.MONTHLY_TYPE:
        delta_time = relativedelta(months=1 * no_periods)
    elif period_type == PeriodType.QUARTERLY_TYPE:
        delta_time = relativedelta(months=3 * no_periods)
    elif period_type == PeriodType.YEARLY_TYPE:
        delta_time = relativedelta(years=1 * no_periods)
    return delta_time


def get_key_from_time(period_type: str, data_time: datetime):
    """
        The function parse data_time and forecasting_type to a key to store in a dictionary
        used for summarized_data

    :param period_type:
    :param data_time:
    :return:
    :rtype:
    """
    key = None
    if period_type == PeriodType.DAILY_TYPE:
        # summarized data by daily
        day = data_time.isocalendar()[1]
        key = day
    elif period_type == PeriodType.WEEKLY_TYPE:
        # summarized data by weekly
        week = data_time.isocalendar()[1]
        key = (week, data_time.isocalendar()[0])
    elif period_type == PeriodType.QUARTERLY_TYPE:
        # summarized data by quarterly
        quarter = int((data_time.month - 1) / 3 + 1)
        key = (quarter, data_time.year)
    elif period_type == PeriodType.MONTHLY_TYPE:
        key = (data_time.month, data_time.year)
    elif period_type == PeriodType.YEARLY_TYPE:
        key = data_time.year
    return key


def convert_from_str_date_to_datetime(str_datetime):
    """
        Convert string have format like describe in DEFAULT_SERVER_DATE_FORMAT to
        variable type datetime

    :param str_datetime:
    :return:
    """
    if str_datetime:
        return datetime.strptime(str_datetime, DEFAULT_SERVER_DATE_FORMAT)
    else:
        return False


def convert_from_datetime_to_str_date(datetime_val):
    """
        Convert datetime variable to string have format like describe in
        DEFAULT_SERVER_DATE_FORMAT

    :param datetime_val:
    :return: convert datetime to string, return False if can not convert
    :rtype: str
    """
    try:
        return datetime.strftime(datetime_val, DEFAULT_SERVER_DATE_FORMAT)
    except Exception as e:
        _logger.exception(e)
        return False


def convert_from_datetime_to_str_datetime(datetime_val):
    """
        Convert datetime variable to string have format like describe in
        DEFAULT_SERVER_DATETIME_FORMAT

    :param datetime_val:
    :return: convert datetime to string, return False if can not convert
    :rtype: str
    """
    try:
        return datetime.strftime(datetime_val, DEFAULT_SERVER_DATETIME_FORMAT)
    except Exception as e:
        _logger.exception(e)
        return False


def convert_from_str_to_datetime(str_datetime):
    """
        Convert datetime_str to datetime
    :param str_datetime
    """
    if str_datetime:
        return datetime.strptime(str_datetime, DEFAULT_SERVER_DATETIME_FORMAT)
    else:
        return False


def list_start_date(from_date: datetime, to_date: datetime, period_type: str) -> List[datetime]:
    """
        The function return list of start date between data range selected from user

    :param from_date:
    :param to_date:
    :param period_type:
    :return:
    """
    from_datetime = from_date
    to_datetime = to_date
    result = []

    if period_type == PeriodType.WEEKLY_TYPE:
        if from_datetime.weekday() != 0:
            from_datetime += timedelta(days=7 - from_datetime.weekday())

        if to_datetime.weekday() != 6:
            to_datetime -= timedelta(days=to_datetime.weekday() + 1)

        result = [dt for dt in
                  rrule(WEEKLY, dtstart=from_datetime, until=to_datetime)]

    elif period_type == PeriodType.MONTHLY_TYPE:
        days_in_month = calendar.monthrange(from_datetime.year, from_datetime.month)[1]

        if from_datetime.day != 1:
            # ignore that month, start with first day of the next month
            from_datetime += timedelta(days=days_in_month - from_datetime.day + 1)

        if to_datetime.day != calendar.monthrange(to_datetime.year, to_datetime.month)[1]:
            to_datetime = datetime(to_datetime.year, to_datetime.month, 1) - timedelta(days=1)

        result = [dt for dt in
                  rrule(MONTHLY, dtstart=from_datetime, until=to_datetime)]

    elif period_type == PeriodType.YEARLY_TYPE:
        if (from_datetime.day, from_datetime.month) != (1, 1):
            # ignore that year, start with first day of the next year
            from_datetime = datetime(from_datetime.year + 1, 1, 1)

        if (to_datetime.day, to_datetime.month) != (31, 12):
            to_datetime = datetime(to_datetime.year - 1, 12, 31)

        result = [dt for dt in
                  rrule(YEARLY, dtstart=datetime(from_datetime.year, 1, 1), until=to_datetime)]

    elif period_type == PeriodType.QUARTERLY_TYPE:
        from_quarter = int((from_datetime.month - 1) / 3 + 1)
        first_month_from_quarter = 1 + (from_quarter - 1) * 3
        to_quarter = int((to_datetime.month - 1) / 3 + 1)
        last_month_to_quarter = 3 + (to_quarter - 1) * 3

        if (from_datetime.day, from_datetime.month) != (1, first_month_from_quarter):
            from_datetime = datetime(from_datetime.year, first_month_from_quarter, 1) + relativedelta(
                months=3)

        if (to_datetime.day, to_datetime.month) != (
                calendar.monthrange(to_datetime.year, last_month_to_quarter)[1], last_month_to_quarter):
            to_datetime = datetime(to_datetime.year, last_month_to_quarter - 2, 1) - relativedelta(
                months=3)

        result = [dt for dt in rrule(MONTHLY, dtstart=from_datetime, until=to_datetime, interval=3)]

    return result


def create_key(forecasting_type, from_date, to_date):
    """
        The function parse data_time and forecasting_type to a key to store in a dictionary
        used for summarized_data

    :param forecasting_type:
    :param from_date:
    :type from_date: datetime
    :param to_date:
    :type to_date:datetime
    :return:
    """
    list_of_start_date = list_start_date(from_date, to_date, forecasting_type)
    dic = OrderedDict.fromkeys([get_key_from_time(forecasting_type, d) for d in list_of_start_date], 0)
    return dic


def get_date_of_month(date):
    return calendar.monthrange(date.year, date.month)[1]


def get_date_of_quarter(date):
    total_date = 0
    for i in range(int(((date.month - 1)/3)*3 + 1), int(((date.month - 1)/3)*3 + 4)):
        total_date += calendar.monthrange(date.year, i)[1]
    return total_date


def get_date_of_year(date):
    return 365 + (calendar.monthrange(date.year, 2)[1] - 28)


def extract_info_in_period(period):
    extract_data = False
    try:
        if period:
            time = period.split(' - ')
            start_time = datetime.strptime(time[0], DEFAULT_SERVER_DATE_FORMAT)
            end_time = datetime.strptime(time[1], DEFAULT_SERVER_DATE_FORMAT)

            number_of_days = (end_time + timedelta(days=1) - start_time).days

            if number_of_days == 7:
                extract_data = end_time, PeriodType.WEEKLY_TYPE
            if 28 <= number_of_days <= 31:
                extract_data = end_time, PeriodType.MONTHLY_TYPE
            if 84 <= number_of_days <= 93:
                extract_data = end_time, PeriodType.QUARTERLY_TYPE
            if number_of_days == 365 or number_of_days == 366:
                extract_data = end_time, PeriodType.YEARLY_TYPE
    except Exception as e:
        _logger.exception('exception: %s' % e)
    return extract_data


def get_first_date_next_period(period_type):
    """ Function get current date of system and generate string have format
    YYYY-MM-DD, that is the first date of next period from current. This is
    used in investment and forecasting report

    :param period_type: daily, weekly, monthly, quarterly, yearly
    :type period_type: str
    :return:
    """
    first_date = get_start_end_date_value(datetime.now(), period_type)[1] + timedelta(days=1)
    return convert_from_datetime_to_str_date(first_date)


def convert_tz(my_timestamp: datetime, new_tz: str= 'UTC', default_cur_tz: str='UTC') -> datetime:
    import pytz  # new import

    old_timezone = my_timestamp.tzinfo

    new_timezone = pytz.timezone(new_tz)
    if old_timezone:
        # returns datetime in the new timezone
        my_timestamp_in_new_timezone = my_timestamp.replace(tzinfo=old_timezone).astimezone(new_timezone)
    else:
        my_timestamp_in_new_timezone = my_timestamp.replace(tzinfo=pytz.timezone(default_cur_tz))\
            .astimezone(new_timezone)

    return my_timestamp_in_new_timezone


def convert_tz_to_utc(my_timestamp):
    """ convert and return the timezone of ``my_timestamp`` to
    UTC

    :param my_timestamp:
    :type my_timestamp: datetime
    :return:
    :rtype: datetime
    """
    return convert_tz(my_timestamp, new_tz='UTC')


def get_no_dates_in_period(date, period_type):
    """

    :param date:
    :type date: datetime
    :param period_type:
    :type period_type: str
    :return:
    """
    return {
        PeriodType.WEEKLY_TYPE: 7,
        PeriodType.MONTHLY_TYPE: get_date_of_month(date),
        PeriodType.QUARTERLY_TYPE: get_date_of_quarter(date),
        PeriodType.YEARLY_TYPE: get_date_of_year(date)
    }.get(period_type, 7)


def convert_number_to_month_name(month_num: int, month_format: str='%b') -> str:
    try:
        month_name = date(1900, month_num, 1).strftime(month_format)
    except Exception as e:
        _logger.exception("Error when convert number to month name.")
        raise e
    return month_name
