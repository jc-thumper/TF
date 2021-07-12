from datetime import timedelta, date
from odoo import _
import calendar
from dateutil.relativedelta import relativedelta


def format_number(number):
    return "{0:,.2f}".format(number)


def get_last_day_month(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def get_list_period_by_type(date_from, date_to, period_type="BY_MONTH"):
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
        start, end = get_start_end_date_value(start, period_type)
        if start < date_from:
            start = date_from
        if end > date_to:
            end = date_to
        list_periods.append((start, end))
        start = end + next
        end = start

    return list_periods


def get_start_end_date_value(date_value, period_type):
    """ Function get the start date_value and end date_value from datetime
    value follow with period_type and return couple of value
    start_date_value and end_date_value type DateTime of date_value follow
    by period_type

    :param date_value:
    :param period_type:
    :return:
    """
    start_date_value = None
    end_date_value = None
    if date_value and period_type:
        if period_type == "BY_MONTH":
            start_date_value = date(date_value.year, date_value.month, 1)
            end_date_value = get_last_day_month(date_value.year, date_value.month)
        elif period_type == "BY_QUARTER":
            month = int((date_value.month - 1) / 3) * 3 + 1
            start_date_value = date(date_value.year, month, 1)

            end_date_value = get_last_day_month(date_value.year, month + 2)
        elif period_type == "BY_YEAR":
            start_date_value = date(date_value.year, 1, 1)
            end_date_value = date(date_value.year, 12, 31)

    return start_date_value, end_date_value


def _divide_line(line, column_number, line_obj):
    """
    Divide a line into 2 lines: title & total.

    :param line: dictionary to render report
    :param column_number: total column in order to set default value
    :param line_obj: financial report line object
    :return: array of 2 dictionary lines
    """
    line1 = {
        'id': line['id'],
        'name': line['name'],
        'level': line['level'],
        'unfoldable': line['unfoldable'],
        'positive': line_obj.green_on_positive,
    }

    # Parent Line Total: Gross Profit...
    line2 = {
        'id': line['id'],
        'total_id': line['id'],
        'formulas': line_obj.formulas.split('=')[1].replace('.balance', ''),
        'code': line_obj.code,
        'name': _('Total') + ' ' + line['name'],
        'class': 'total',
        'level': line['level'] + 1,
        'columns': [{'name': 0} for i in range(column_number)],
        'positive': line_obj.green_on_positive,
    }
    return [line1, line2]


def _get_balance_sheet_value(line, financial_report, currency_table, daterange_list, analytic_account_id, last_year=None):
    """
    Function to get actual balance in Balance Sheet report
    :return: dictionary of value line for each period
    """
    res = []
    debit_credit = False
    domain_ids = {'line'}

    for item in daterange_list:
        linesDicts = [[{}]]
        date_to = item[1] - relativedelta(years=1) if last_year else item[1]
        date_from, date_to, strict_range = line.with_context(date_from=False, date_to=date_to)._compute_date_range()
        r = line.with_context(date_from=False, date_to=date_to,
                              strict_range=strict_range,
                              analytic_account_ids = analytic_account_id)._eval_formula(financial_report,
                                                                       debit_credit,
                                                                       currency_table,
                                                                       linesDicts[0])
        res.extend(r)
        for column in r:
            domain_ids.update(column)

    balance_sheet_dict = line._put_columns_together(res, domain_ids)
    return balance_sheet_dict
