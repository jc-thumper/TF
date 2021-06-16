# -*- coding: utf-8 -*-

from ...si_core.utils.string_utils import PeriodType

CORRECT_PERIOD_TYPE = {
    'hour': PeriodType.HOURLY_TYPE,
    'day': PeriodType.DAILY_TYPE,
    'week': PeriodType.WEEKLY_TYPE,
    'month': PeriodType.MONTHLY_TYPE,
    'year': PeriodType.YEARLY_TYPE,
    'quarter': PeriodType.QUARTERLY_TYPE,
    'biweek': PeriodType.BIWEEKLY
}


def get_correct_period_type(period_type):
    """
        Convert the period_type argument to the correct period type which is defined in
        string_utils in SI Core module
    :param period_type:
    :type period_type:
    :return:
    :rtype:
    """
    lowercase_period_type = period_type.lower()
    return CORRECT_PERIOD_TYPE.get(lowercase_period_type, None)

