# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import numbers
import base64
from datetime import datetime
import logging

from odoo import api, models, fields, tools, modules, _
from odoo.addons.account_reports.models.account_financial_report import FormulaLine
from odoo.tools.safe_eval import safe_eval
from odoo.tools.float_utils import float_compare

from ..utils.utils import format_percentage, get_eval_context, get_short_currency_amount, format_currency
from ..utils.time_utils import BY_DAY, BY_WEEK, BY_MONTH, BY_QUARTER, BY_YEAR, BY_YTD, get_start_end_date_value_with_delta

_logger = logging.getLogger(__name__)

NUM_KPIS = 6
DEFAULT_SYMBOL = '-'

PERCENTAGE = 'percentage'
CURRENCY = 'currency'


class KPIJournal(models.Model):
    _name = "kpi.journal"
    _description = "KPI journal"

    def _get_default_image(self, module, path, name):
        image_path = modules.get_module_resource(module, path, name)
        return tools.image_process(base64.b64encode(open(image_path, 'rb').read()), size=(1024, 1024))
        # return tools.image_resize_image_big(base64.b64encode(open(image_path, 'rb').read()))

    periods_type = [
        (BY_DAY, 'Daily'),
        (BY_WEEK, 'Weekly'),
        (BY_MONTH, 'Monthly'),
        (BY_QUARTER, 'Quarterly'),
        (BY_YEAR, 'Yearly'),
        (BY_YTD, 'Year To Date')
    ]

    units_type = [
        (PERCENTAGE, 'Percentage'),
        (CURRENCY, 'Currency'),
    ]

    name = fields.Char('KPI Name')
    selected = fields.Boolean('KPI will appear', default=False)
    data = fields.Char('Json render', default='')
    order = fields.Integer('Order position', default=-1)
    code_name = fields.Char('KPI Code Name', require=True)
    color = fields.Char(default='#9fc5f8')
    icon_kpi = fields.Binary('Icon KPI', attachment=True,
                             default=lambda self: self._get_default_image('account_dashboard', 'static/src/img', 'default_icon.png'))
    period_type = fields.Selection(periods_type, default=BY_YTD)
    code_compute = fields.Char(default="result = 0")
    unit = fields.Selection(units_type, default=CURRENCY)
    default_kpi = fields.Boolean("Is Default KPI", default=False, readonly=True)
    green_on_positive = fields.Boolean(string='Is growth good when positive?', default=True)

    def generate_data_kpi(self):
        # call <name>_kpi_generate_data to update the the kpi dashboard
        cust_method_name = '{}_kpi_generate_data'.format(self.provider)
        if hasattr(self, cust_method_name):
            method = getattr(self, cust_method_name)
            # values = method(values)

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    @api.model
    def kpi_render(self, kpis_info):
        """ Function get the Json to render the kpi header with each kpi was
        showed at head and the data will render to setting kpi view

        :param kpis_info: type "personalized.kpi.info"
        :return:
        """
        print('kpi_render')
        kpi_data = {}
        kpi_content = self.get_kpi_content_render(kpis_info)
        kpi_data['kpi_data'] = kpi_content
        kpi_info = self.get_kpi_info(kpis_info)
        kpi_data['kpi_info'] = kpi_info

        return kpi_data

    def get_kpi_content_render(self, kpis_info):
        """ Function return the JSON to render the kpi header

        :return:
        """
        kpi_render = []
        # Select all kpi have been chosen and render it to header
        kpis = kpis_info.filtered('selected').sorted('order')
        dict_context = get_eval_context(self, 'kpi.journal')

        # Dictionary have structure with key is the range time and the value is the normal
        # dict_line defined in FormularLine class. dict_line is a dictionary with key is
        # code of a group and value is tuple value (balance, credit, debit)
        dict_lines_data = {}

        for kpi in kpis:
            kpi_value = self.get_data_kpi_render(kpi, dict_context, dict_lines_data)
            if kpi_value:
                kpi_render.append(kpi_value)
        return kpi_render

    def get_kpi_info(self, kpis_info):
        kpi_info = {'kpi_selections': self.get_kpi_selection(kpis_info),
                    'kpi_selected': self.get_kpi_selected(kpis_info)}

        return kpi_info

    def get_kpi_selection(self, kpis_info):
        kpi_selection = []
        for kpi in kpis_info:
            kpi_selection.append({
                'name': kpi.kpi_id.name,
                'selected': kpi.selected
            })
        return kpi_selection

    def get_kpi_selected(self, kpis_info):
        kpi_selected = []
        kpis = kpis_info.filtered('selected').sorted('order')
        for kpi in kpis:
            kpi_selected.append(kpi.kpi_id.name)
        return kpi_selected

    def get_json_kpi_info(self, kpi_ids, delta_periods=0, lines_dict={}):
        """ Function return a json which is information of data will show in view.
        it's used to render in email template.

        :return:
        """
        dict_context = get_eval_context(self, 'kpi.journal')
        data_kpi_usa_company_insight = {}

        kpis_info = self.search([('id', 'in', kpi_ids)])
        for kpi in kpis_info:
            start, end = get_start_end_date_value_with_delta(self, datetime.now(), kpi.period_type, delta_periods)

            dict_context['date_from'] = start
            dict_context['date_to'] = end

            # change lines_dict of dict_context
            dict_context['lines_dict'] = lines_dict

            safe_eval(kpi.code_compute, dict_context, mode="exec", nocopy=True)
            value = dict_context.get('result', DEFAULT_SYMBOL)
            if not value:
                value = 0.0
            data_kpi_usa_company_insight[kpi.code_name] = {
                'value': value,
                'name': kpi.name,
                'type': kpi.unit,
                'period_type': dict(kpi.periods_type).get(kpi.period_type)
            }
        return data_kpi_usa_company_insight

    ########################################################
    # KPI GENERATOR
    ########################################################
    def get_data_kpi_render(self, info, dict_context, dict_lines_data):
        """ Function support return the dictionary is the data to render a kpi item
        that contain the data in 'info' variable

        :param dict_lines_data:
        :param dict_context:
        :param info:
        :return:
        """

        kpi_info_detail = info.kpi_id

        # append current time range to dict_context
        self.append_data_follow_range_time(dict_context, kpi_info_detail.period_type, delta_periods=0, lines_dict=dict_lines_data)
        comparison = ''
        comparison_title = ''
        trend = ''

        try:
            safe_eval(kpi_info_detail.code_compute, dict_context, mode="exec", nocopy=True)
            value = dict_context.get('result', DEFAULT_SYMBOL) + 0

            formatted_value, short_title = self.format_number_type(value, kpi_info_detail.unit)

            # PROGRESS FOR PREVIOUS PERIOD
            # append range time of previous period
            self.append_data_follow_range_time(dict_context, kpi_info_detail.period_type, delta_periods=-1, lines_dict=dict_lines_data)

            # compute result for previous period
            safe_eval(kpi_info_detail.code_compute, dict_context, mode="exec", nocopy=True)
            previous_period_value = dict_context.get('result', DEFAULT_SYMBOL) + 0
            if isinstance(previous_period_value, numbers.Number):
                minus_value = value - previous_period_value
                formatted_minus_value, short_minus_title = self.format_number_type(minus_value, kpi_info_detail.unit)
                comparison += short_minus_title + _(' vs prior period')
                comparison_title += formatted_minus_value + _(' vs prior period')
                
                if float_compare(minus_value, 0, precision_rounding=2) > 0:
                    icon = kpi_info_detail.green_on_positive and 'up_green' or 'up_red'
                elif float_compare(minus_value, 0, precision_rounding=2) < 0:
                    icon = kpi_info_detail.green_on_positive and 'down_red' or 'down_green'
                else:
                    icon = 'no_change'
                
                trend = '/account_dashboard/static/src/img/{}.png'.format(icon)
        except:
            formatted_value = '-'
            short_title = '-'
            _logger.warning("Parse Fail!")

        kpi_data_render = {
            'label': kpi_info_detail.name,
            'color': info.color,
            'value': formatted_value,
            'short_title': short_title,
            'comparison': comparison,
            'comparison_title': comparison_title,
            'period_type': info.period_type.upper(),
            'trend': trend,
            'icon': 'web/image?model={model}&field=icon_kpi&id={id}&unique='.format(model=info._name, id=info.id)
        }

        return kpi_data_render

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    def get_group_in_period(self, group_name, report_name, date_from=None, date_to=None, lines_dict={}):
        """

        :param lines_dict:
        :param group_name: name of group show in the report
            Ex: Net Profit, Expenses
        :param report_name: name the report containing the group above
            Ex: Profit and Loss, Cash Flow
        :param date_from: the start point to summarize data for the group
        :param date_to: the end point to summarize data for the group
        :return:
        """
        return_value = None
        modelAFHR = self.env['account.financial.html.report']
        modelAFHRL = self.env['account.financial.html.report.line']
        financial_report = modelAFHR.search([('name', '=', report_name)])
        if len(financial_report) == 1:
            cur_group = modelAFHRL.search([('name', '=', group_name)])
            if len(cur_group) > 1:
                result_group = []
                # loop each group when it return multiple group have same name
                for idx, group in enumerate(cur_group):
                    while group.parent_id:
                        group = group.parent_id
                    if group.financial_report_id and group.financial_report_id.id == financial_report.id:
                        result_group = cur_group[idx]
                cur_group = result_group

            if len(cur_group) == 1:
                if lines_dict.get(cur_group.code, False):
                    return_value = lines_dict[cur_group.code]
                else:
                    currency_table = modelAFHR._get_currency_table()
                    if date_from and date_to:
                        cur_group = cur_group.with_context(strict_range=False, date_from=str(date_from),
                                                           date_to=str(date_to), state='posted')
                    return_value = FormulaLine(cur_group, currency_table, financial_report, linesDict=lines_dict)

        return return_value

    def append_data_follow_range_time(self, dict_context, type_period, delta_periods=0, lines_dict={}, company_id=None):
        """ Function change data in the dict_context variable base on range time

        :param lines_dict:
        :param dict_context:
        :param type_period:
        :param delta_periods:
        :return:
        """
        if company_id:
            old_comp_id = self.env.company.id
            self.env.company = company_id
        from_date, to_date = get_start_end_date_value_with_delta(self, datetime.now(), type_period, delta_periods)

        # Change range time data
        dict_context['date_from'] = str(from_date.date())
        dict_context['date_to'] = str(to_date.date())

        # change lines_dict of dict_context
        dict_context['lines_dict'] = lines_dict.setdefault((dict_context['date_from'], dict_context['date_to']), {})

        if company_id:
            self.env.company = old_comp_id

    def format_number_type(self, value, unit_type):
        """ Function is the middle layer between layout and utils. It will receive value
        and unit_type, and then return a string is value have been formatted

        :param value:
        :param unit_type:
        :return:
        """
        formatted_value = short_title = ''
        if unit_type == CURRENCY:
            formatted_value = format_currency(self, value)
            short_title = get_short_currency_amount(value, self.env.company.currency_id)

        elif unit_type == PERCENTAGE:
            formatted_value = format_percentage(value)
            short_title = formatted_value

        return formatted_value, short_title
