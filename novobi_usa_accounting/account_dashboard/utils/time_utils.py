# -*- coding: utf-8 -*-

import calendar

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import timedelta, datetime, date
from dateutil.rrule import rrule, WEEKLY, MONTHLY, YEARLY
from dateutil.relativedelta import *
from collections import OrderedDict

# Constant value
SHORT_DATETIME_FORMAT = "%b %d"
APPEAR_DATE_FORMAT = "%m/%d/%Y"
BY_DAY = "day"
BY_WEEK = "week"
BY_MONTH = "month"
BY_QUARTER = "quarter"
BY_YEAR = "year"
BY_YTD = "ytd"
BY_MTD = 'mtd'
BY_FISCAL_YEAR = "fiscal_year"


def convert_format_time(data_time):
    """ Function return value of @param: date_time (standard format)
    to sort format %b %d (Ex: Feb 28)

    :param data_time:
    :return:
    """
    date_time_value = convert_from_str_to_datetime(data_time)
    return date_time_value.strftime(SHORT_DATETIME_FORMAT)


def convert_from_str_to_datetime(str_datetime):
    """ Function convert string have format like describe in
    DEFAULT_SERVER_DATE_FORMAT to variable type datetime

    :param str_datetime:
    :return:
    """
    return datetime.strptime(str_datetime, DEFAULT_SERVER_DATE_FORMAT)


def get_start_end_date_value(self, date_value, period_type):
    """ Function get the start date_value and end date_value from datetime
    value follow with period_type and return couple of value
    start_date_value and end_date_value type DateTime of date_value follow
    by period_type

    :param self:
    :param date_value:
    :param period_type:
    :return:
    """
    start_date_value = None
    end_date_value = None
    if date_value and period_type:
        if period_type == BY_DAY:
            start_date_value = date_value
            end_date_value = date_value
        elif period_type == BY_WEEK:
            # get Monday of (week, year)
            date_delta = date_value.isoweekday()
            start_date_value = date_value - timedelta(days=(date_delta - 1))
            end_date_value = date_value + timedelta(days=(7 - date_delta))
        elif period_type == BY_MONTH:
            start_date_value = datetime(date_value.year, date_value.month, 1)
            end_date_value = datetime(date_value.year, date_value.month,
                                      calendar.monthrange(date_value.year, date_value.month)[1])
        elif period_type == BY_QUARTER:
            month = int((date_value.month - 1) / 3) * 3 + 1
            start_date_value = datetime(date_value.year, month, 1)

            end_date_value = datetime(date_value.year, month + 2, calendar.monthrange(date_value.year, month + 2)[1])
        elif period_type == BY_YEAR:
            start_date_value = datetime(date_value.year, 1, 1)
            end_date_value = datetime(date_value.year, 12, 31)
        elif period_type == BY_YTD:
            current_date = datetime.now()
            company_fiscalyear_dates = self.env.user.company_id.compute_fiscalyear_dates(date_value)
            start_date_value = datetime.combine(company_fiscalyear_dates['date_from'], datetime.min.time())
            raw_end_date_value = company_fiscalyear_dates['date_to']
            end_date_value = datetime(raw_end_date_value.year, current_date.month, current_date.day)
        elif period_type == BY_FISCAL_YEAR:
            company_fiscalyear_dates = self.env.user.company_id.compute_fiscalyear_dates(date_value)
            start_date_value = datetime.combine(company_fiscalyear_dates['date_from'], datetime.min.time())
            end_date_value = datetime.combine(company_fiscalyear_dates['date_to'], datetime.min.time())
        elif period_type == BY_MTD:
            end_date_value = date_value
            start_date_value = end_date_value - relativedelta(days=(end_date_value.day - 1))

    return start_date_value, end_date_value


def get_start_end_date_value_with_delta(self, date_value, period_type, time_delta):
    start, end = get_start_end_date_value(self, date_value, period_type)
    times = abs(time_delta)
    while times > 0:
        times -= 1
        start, end = get_start_end_date_value(self, start + timedelta(days=1 if time_delta > 0 else -1), period_type)
    return start, end


def get_same_date_delta_period(date_value, month=0, day=0):
    same_date_result = date_value
    if not 1 <= month <= 12:
        month = date_value.month
    if day >= 1:
        fail_convert = True
        while fail_convert:
            try:
                same_date_result = date_value.replace(day=day, month=month)
                fail_convert = False
            except:
                day -= 1
    return same_date_result


def list_start_date(from_date, to_date, period_type):
    """ Function the function return list of start date between data
    range selected from user

    :param from_date:
    :param to_date:
    :param period_type:
    :return:
    """
    from_datetime = convert_from_str_to_datetime(from_date)
    to_datetime = convert_from_str_to_datetime(to_date)
    if period_type == BY_WEEK:
        if from_datetime.weekday() != 0:
            from_datetime += timedelta(days=7 - from_datetime.weekday())
        if to_datetime.weekday() != 6:
            to_datetime -= timedelta(days=to_datetime.weekday() + 1)
        return [dt for dt in
                rrule(WEEKLY, dtstart=from_datetime, until=to_datetime)]
    elif period_type == BY_MONTH:
        days_in_month = calendar.monthrange(from_datetime.year, from_datetime.month)[1]
        if from_datetime.day != 1:
            # ignore that month, start with first day of the next month
            from_datetime += timedelta(days=days_in_month - from_datetime.day + 1)
        if to_datetime.day != calendar.monthrange(to_datetime.year, to_datetime.month)[1]:
            to_datetime = datetime(to_datetime.year, to_datetime.month, 1) - timedelta(days=1)
        return [dt for dt in
                rrule(MONTHLY, dtstart=from_datetime, until=to_datetime)]
    elif period_type == BY_YEAR:
        if (from_datetime.day, from_datetime.month) != (1, 1):
            # ignore that year, start with first day of the next year
            from_datetime = datetime(from_datetime.year + 1, 1, 1)
        if (to_datetime.day, to_datetime.month) != (31, 12):
            to_datetime = datetime(to_datetime.year - 1, 12, 31)
        return [dt for dt in
                rrule(YEARLY, dtstart=datetime(from_datetime.year, 1, 1), until=to_datetime)]
    elif period_type == BY_QUARTER:
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
        return [dt for dt in rrule(MONTHLY, dtstart=from_datetime, until=to_datetime, interval=3)]


def get_key_from_time(period_type, data_time):
    """ The function parse data_time and period_type to a key to
    store in a dictionary used for summarized_data

    :type period_type: str
    :type data_time: datetime
    :return: tuple or number depends on period_type
    """
    key = None
    if period_type == 'weekly':
        # summarized data by weekly
        week = data_time.isocalendar()[1]
        key = (week, data_time.isocalendar()[0])
    elif period_type == 'quarterly':
        # summarized data by quarterly
        quarter = int((data_time.month - 1) / 3 + 1)
        key = (quarter, data_time.year)
    elif period_type == 'monthly':
        key = (data_time.month, data_time.year)
    elif period_type == 'yearly':
        key = data_time.year
    return key


def create_key(period_type, from_date, to_date):
    """ Function the function initial a dictionary to store summarized data
    depends on period_type and date range selected by user

    :param period_type:
    :param from_date:
    :param to_date:
    :return:
    """
    list_of_start_date = list_start_date(from_date, to_date, period_type)
    dic = OrderedDict.fromkeys([get_key_from_time(period_type, d) for d in list_of_start_date], 0)
    return dic


def get_date_of_month(date):
    return calendar.monthrange(date.year, date.month)[1]


def get_date_of_quarter(date):
    sum = 0
    q = ((date.month - 1) / 3) * 3 + 1
    for i in range(int(((date.month - 1) / 3) * 3 + 1), int(((date.month - 1) / 3) * 3 + 4)):
        sum += calendar.monthrange(date.year, i)[1]
    return sum


def get_date_of_year(date):
    return 365 + (calendar.monthrange(date.year, 2)[1] - 28)


def extract_info_in_period(period):
    try:
        time = period.split(' - ')
        start_time = datetime.strptime(time[0], DEFAULT_SERVER_DATE_FORMAT)
        end_time = datetime.strptime(time[1], DEFAULT_SERVER_DATE_FORMAT)

        number_of_days = (end_time + timedelta(days=1) - start_time).days

        if number_of_days == 7:
            return end_time, BY_WEEK
        if number_of_days >= 28 and number_of_days <= 31:
            return end_time, BY_MONTH
        if number_of_days >= 84 and number_of_days <= 93:
            return end_time, BY_QUARTER
        if number_of_days == 365 or number_of_days == 366:
            return end_time, BY_YEAR
    except:
        return False


def get_list_period_by_type(self, date_from, date_to, period_type=BY_MONTH):
    """ Function return list of periods base on start, end time and
    type of period to generate periods have sorted and lie between
    start and end date

    :param date_from: datetime
    :param date_to: datetime
    :param period_type:
    :return: list of tuples date value: start date and end date.
            both of them is date type
    """
    next = timedelta(days=1)
    start = date_from
    end = date_from
    list_periods = []
    while end <= date_to:
        start, end = get_start_end_date_value(self, start, period_type)
        if start < date_from:
            start = date_from
        if end > date_to:
            end = date_to
        list_periods.append((start.date(), end.date()))
        start = end + next
        end = start

    return list_periods
