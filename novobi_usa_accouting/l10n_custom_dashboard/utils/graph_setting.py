########################################################################################################################
# General settings for ChartJs have been configured in account_dashboard.js
# This file is used to add more custom setting to ChartJs
# Ref: https://www.chartjs.org/docs/latest/configuration/
########################################################################################################################

# graph_data structure for bar chart
# GRAPH_DATA = [
#     {
#         'label': 'LABEL1',
#         'backgroundColor': '#COLOR1',
#         'data': [0, 2, 45]
#     },
#     {
#         'label': 'LABEL2',
#         'backgroundColor': '#COLOR2',
#         'data': [20, 2, 4]
#     },
# ]

# graph_data structure for line chart
# GRAPH_DATA = [
#     {
#         'label': line['key'],
#         'data': list(map(lambda item: item['y'], line['values'])),
#         'borderColor': COLOR_OPEN_INVOICES,
#         'fill': True,
#         'lineTension': 0
#     },
#     { ... }
# ]
from odoo.tools import formatLang


def format_currency(self, value):
    currency = self.env.user.company_id.currency_id
    return_value = formatLang(self.env, currency.round(value) + 0.0, currency_obj=currency)
    return return_value


# GRAPH SETTING
def get_normal_barchart_setting(mode='nearest', stacked=False, reverse=False):
    return {
        'tooltips': {
            'mode': mode    # This param is to show multi individual labels in same stacked bar in the same tooltip.
        },
        'scales': {
            'yAxes': [{'stacked': stacked}],
            'xAxes': [{'stacked': stacked}]
        },
        'legend': {
            'reverse': reverse,
        }
    }


def get_horizontal_barchart_setting(stacked=False, position='top'):
    return {
        'tooltips': {
            'mode': 'y'
        },
        'legend': {
            'position': position,
            'align': 'end',
        },
        'scales': {
            'xAxes': [{
                'stacked': stacked,
                'display': stacked,
                'ticks': {
                    'beginAtZero': True
                }
            }],
            'yAxes': [{
                'stacked': stacked,
                'display': stacked,
            }]
        }
    }


def get_barchart_setting(mode='nearest', stacked=False, horizontal=False, reverse=False):
    return get_horizontal_barchart_setting(stacked) if horizontal else get_normal_barchart_setting(mode, stacked, reverse)


def get_linechart_setting(mode='nearest', stacked=False, horizontal=False):
    return get_barchart_setting(mode, stacked, horizontal)


def get_chartjs_setting(chart_type, mode='nearest', stacked=False, horizontal=False, reverse=False):
    if chart_type == 'line':
        return get_linechart_setting(mode, stacked, horizontal)
    else:
        return get_barchart_setting(mode, stacked, horizontal, reverse)


# GRAPH FORMAT
def get_barchart_format(data, label, color, order=0):
    return {
        'data': data,
        'label': label,
        'borderColor': color,
        'backgroundColor': color,
        'order': order,
    }


def get_linechart_format(data, label, color, background_color=False, fill=False, border_width=2, line_tension=0, order=0):
    background_color = (background_color or color) if fill else '#fff'
    return {
        'data': data,
        'label': label,
        'borderColor': color,
        'backgroundColor': background_color,
        'borderWidth': border_width,
        'fill': fill,
        'lineTension': line_tension,
        'order': order,
        'type': 'line'
    }


def get_piechart_format(data, background_color):
    return {
        'data': data,
        'backgroundColor': background_color,
    }


def get_info_data(self, name, total_value):
    return {
        'name': name,
        'summarize': format_currency(self, total_value)
    }


def get_chart_json(data, label, setting, info_data=[]):
    return {
        'data': data,
        'label': label,
        'setting': setting,
        'info_data': info_data,
    }
