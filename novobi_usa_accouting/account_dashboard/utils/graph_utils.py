from datetime import datetime

from .time_utils import BY_DAY, BY_WEEK, BY_MONTH, BY_QUARTER, BY_YEAR, \
    get_start_end_date_value_with_delta, get_same_date_delta_period, get_list_period_by_type


def get_json_render(data_type, extend, label, data_render,
                    name_card, selection, function_retrieve,
                    extra_param, setting={}):
    return [{
        'function_retrieve': function_retrieve,
        'data_type': data_type,
        'extend': extend,
        'label': label,
        'data': data_render,
        'name': name_card,
        'selection': selection,
        'extra_param': extra_param,
        'setting': setting
    }]


def get_json_data_for_selection(self, selection, periods, default_selection):
    """ Function return json setting for fields selection time, that defined
    in variables "period_by_month" and "period_by_complex"

    :param periods:
    :param selection:
    :return:
    """

    for period in periods:
        start, end = get_start_end_date_value_with_delta(self, datetime.now(), period['t'], period['d'])

        # If period is compute to today we will convert the end day to the date of same period
        if period.get('td', False):
            month = 0
            if period['t'] == BY_QUARTER:
                month = end.month - (datetime.now().month%3 - 3)
            elif period['t'] == BY_YEAR:
                month = datetime.now().month
            end = get_same_date_delta_period(end, day=datetime.now().day, month=month)

        period_selection = {
            'n': period['n'],  # What will show in selection field
            's': start.strftime('%Y-%m-%d'),  # start date of that period base on current time
            'e': end.strftime('%Y-%m-%d'),  # end date of that period base on current time
            'd': period['n'] == default_selection  # var bool to check what will be chosen defaultly
        }

        # Append and setting for case return the type period used to group in data return
        # instead of by month in default
        if period.setdefault('k', BY_MONTH):
            period_selection['k'] = period['k']
        selection.append(period_selection)


def get_chart_point_name(list_time_name, period_type):
    """ Function support return the label that will show on each point in chart
     base on list_time_name value and type of period defined in period_type

    :param list_time_name:
    :param period_type:
    :return:
    """
    name = ""
    if len(list_time_name):
        if period_type == BY_DAY:
            date_point = list_time_name[0]
            name = '%s %s/%s' % (date_point.strftime('%a'), date_point.month, date_point.day)
        elif period_type == BY_WEEK:
            first_date = list_time_name[0]
            second_date = list_time_name[1]
            name = '%s-%s' % (first_date.strftime('%d %b'), second_date.strftime('%d %b'))
        elif period_type == BY_MONTH:
            date_point = list_time_name[0]
            name = date_point.strftime('%b %Y')
        elif period_type == BY_QUARTER:
            date_point = list_time_name[0]
            quarter = int((date_point.month - 1) / 3) + 1
            name = 'Q%s %s' % (quarter, date_point.year)
        elif period_type == BY_YEAR:
            date_point = list_time_name[0]
            name = date_point.strftime('%Y')

    return name


def get_data_for_graph(self, date_from, date_to, period_type, data_group, fields=[], date_field='date_in_period', pos=1):
    """
    Used in retrieve_profit_and_loss(), to pass data from data_group and return graph data.
    :param self: usa.journal record
    :param date_from:
    :param date_to:
    :param period_type:
    :param data_group:
    :param fields: list contains name of fields to get data from data_group
    :param date_field:
    :param pos: to determine that value is negative or positive
    :return: (
        summarize: to use in info_data
        list_data_return: list to use in graph_data
        graph_label: list of labels to pass to get_chart_json()
    )
    """
    index_period = 0
    length = len(fields)
    list_data_return = []
    summarize = []
    graph_label = []

    if length:
        periods = get_list_period_by_type(self, date_from, date_to, period_type)
        list_zero_value = [0 for i in range(length)]
        list_data_return = [[] for i in range(length)]
        summarize = list_zero_value.copy()

        for data in data_group:
            list_data_value = [data[key] * pos for key in fields]
            while not (periods[index_period][0] <= data[date_field] <= periods[index_period][1]) and index_period < len(periods):
                for item in list_data_return:
                    item.append(0)
                graph_label.append(get_chart_point_name(periods[index_period], period_type))
                index_period += 1
            if index_period < len(periods):
                for i in range(length):
                    list_data_return[i].append(list_data_value[i])
                graph_label.append(get_chart_point_name(periods[index_period], period_type))
                summarize = [sum(x) for x in zip(summarize, list_data_value)]
                index_period += 1

        while index_period < len(periods):
            for item in list_data_return:
                item.append(0)
            graph_label.append(get_chart_point_name(periods[index_period], period_type))
            index_period += 1

    return summarize, list_data_return, graph_label


def append_data_fetch_to_list(data_list, graph_label, periods, period_type, index, values=None):
    """
    For each data from data_fetch, append its to data_list and graph_label
    :param data_list: list to use in graph_data
    :param graph_label: list of labels to pass to get_chart_json()
    :param periods: list of periods
    :param period_type:
    :param index: from 0 to len(periods)
    :param values: values to put to data_list. If len(data_list) = n, default of values will be a list contains n zero.
    """
    length = len(data_list)
    values = values or [0] * length
    for i in range(length):
        data_list[i].append(values[i])
    graph_label.append(get_chart_point_name(periods[index], period_type))
