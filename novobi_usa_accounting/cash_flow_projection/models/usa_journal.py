# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import api, fields, models, _
from datetime import datetime
from odoo.addons.account_dashboard.models.usa_journal import COLOR_PROJECTED_CASH_IN, COLOR_PROJECTED_CASH_OUT, \
    COLOR_PROJECTED_BALANCE, CASH_FORECAST
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.addons.l10n_custom_dashboard.utils.graph_setting import format_currency, get_chartjs_setting, get_linechart_format, \
    get_barchart_format, get_info_data, get_chart_json


class UsaJournal(models.Model):
    _inherit = 'usa.journal'
    
    def action_open_cashflow_forecast_summary(self):
        self.env.company.cash_flow_last_period_type = 'month'
        action = self.env.ref('cash_flow_projection.cash_flow_projection_action_client').read()[0]
        return action
    
    @api.model
    def retrieve_cash_forecast(self, date_from, date_to, period_type):
        open_balance_date = datetime.today()
        cash_in = []
        cash_out = []
        net_cash = []
        # Get record options
        record_options = self.env['cash.flow.transaction.type'].get_all_record()
        record_options.update({
            'period': 'month',
            'num_period': 7,
            'from_chart': True,
        })
        # Retrieve data from cash flow projection
        result_dict, num_period, period_unit = self.env['cash.flow.projection'].get_data(record_options)
        data_dict = result_dict.get('periods') or []
        graph_label = [data.get('period', '') for data in data_dict]
        opening_balance = len(data_dict) > 0 and data_dict[0].get('opening_balance') or 0.0
        for period in data_dict:
            cash_in.append(period.get('total_cash_in', 0))
            cash_out.append(-period.get('total_cash_out', 0))
            net_cash.append(period.get('closing_balance', 0))
        
        graph_data = [
            get_linechart_format(net_cash, _('Balance Carried Forward'), COLOR_PROJECTED_BALANCE, order=2),
            get_barchart_format(cash_out, _('Projected Cash out'), COLOR_PROJECTED_CASH_OUT, order=1),
            get_barchart_format(cash_in, _('Projected Cash in'), COLOR_PROJECTED_CASH_IN),
        ]
        
        info_data = [
            get_info_data(self, _('Total Projected Cash in'), sum(cash_in)),
            get_info_data(self, _('Total Projected Cash out'), sum(cash_out)),
            get_info_data(self, _(
                'Balance as of {}'.format(open_balance_date.strftime(DEFAULT_SERVER_DATE_FORMAT))),
                          opening_balance),
        ]
        
        return get_chart_json(graph_data, graph_label,
                              get_chartjs_setting(chart_type='bar', mode='index', stacked=True, reverse=True),
                              info_data)
    
    def open_action_label(self):
        """ Function return action based on type for related journals

        :return:
        """
        
        if self.type == CASH_FORECAST:
            return self.action_open_cashflow_forecast_summary()
        else:
            return super().open_action_label()
