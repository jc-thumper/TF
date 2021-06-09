# -*- coding: utf-8 -*-

from datetime import timedelta, datetime
from ...si_core.utils.datetime_utils import convert_from_datetime_to_str_datetime, get_start_end_date_value
from ...si_core.utils.string_utils import PeriodType


def find_index_of_time_range(date_value, date_range):
    """
        Find the index of the date_value in date_range
    :param date_value:
    :type date_value: datetime
    :param date_range:
    :type date_range: list[(datetime, datetime)]
    :return:
    :rtype: int
    """
    index = 0
    for start_date, end_date in date_range:
        if start_date <= date_value <= end_date:
            return index

        index += 1

    return -1


def get_date_range_for_all_period_dict(number_of_cols, date_value=None):
    """

    :param number_of_cols:
    :type number_of_cols: int
    :param date_value:
    :type date_value: datetime
    :return: {
        'daily': [(start_date, end_date), ...],
        'weekly': [((start_date, end_date), ...)],
        ...
    }
    :rtype: (dict, dict)
    """
    date_value = date_value or datetime.now()

    date_range_dict = {
        period_type: get_date_range_by_num_of_cols(date_value, period_type, number_of_cols)
        for period_type, _ in PeriodType.LIST_PERIODS
    }
    date_range_str_dict = {
        period_type: get_date_range_by_num_of_cols(date_value, period_type, number_of_cols, True)
        for period_type, _ in PeriodType.LIST_PERIODS
    }

    return date_range_dict, date_range_str_dict


def get_date_range_by_num_of_cols(date_value, period_type, number_of_cols, value_in_string=None):
    """
        Return the list of start_date, end_date by period_type and num_of_cols
    :param date_value:
    :type date_value: datetime
    :param period_type:
    :type period_type: datetime
    :param number_of_cols:
    :type number_of_cols: int
    :param value_in_string:
    :type value_in_string: bool
    :return:
    :rtype: list[(datetime, datetime)]
    """
    date_range = []

    first_day, last_day = get_start_end_date_value(date_value, period_type)
    for columns in range(number_of_cols):
        first_day_in_date = first_day.date()
        last_day_in_date = last_day.date()
        if value_in_string:
            date_range.append(
                (
                    convert_from_datetime_to_str_datetime(first_day_in_date),
                    convert_from_datetime_to_str_datetime(last_day_in_date)
                )
            )
        else:
            date_range.append((first_day_in_date, last_day_in_date))
        first_day, last_day = get_start_end_date_value(last_day + timedelta(days=1), period_type)

    return date_range
