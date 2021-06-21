# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import ast

from datetime import datetime, timedelta

from ..utils.time_utils import get_start_end_date_value_with_delta
from ..utils.time_utils import get_start_end_date_value, BY_YTD
from ..utils.utils import get_eval_context, convert_value_with_unit_type, format_human_readable_amount
from ..models.kpi_journal import DEFAULT_SYMBOL
from odoo import api, fields, models, tools
from odoo.exceptions import AccessError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class Digest(models.Model):
    _inherit = 'digest.digest'
    _description = 'Extend Digest'

    kpi_usa_company_insight = fields.Boolean('Company Insight')
    kpi_usa_company_insight_value = fields.Char(compute='_compute_kpi_usa_company_insight_value')

    ########################################################
    # COMPUTED FUNCTION
    ########################################################
    def _compute_kpi_usa_company_insight_value(self):
        for record in self:
            company = self._context.get('company')
            delta_periods = self._context.get('delta_periods')
            lines_dict = {}

            if company and type(delta_periods) is int:
                dict_context = get_eval_context(self, 'kpi.journal')
                data_kpi_usa_company_insight = {}
                user_id = self.env.user.id
                company_id = self.sudo().company_id.id

                model_PKI = self.env['personalized.kpi.info']
                model_PKI.generate_kpi_for_new_user(user_id, company.id)
                kpis_info = model_PKI.search([
                    ('user_id', '=', user_id),
                    ('company_id', '=', company.id),
                    ('selected', '=', True)
                ])
                data_kpi_usa_company_insight.setdefault(user_id, {})

                for kpi in kpis_info:
                    kpi_info_detail = kpi.kpi_id
                    start, end = get_start_end_date_value_with_delta(self, datetime.now(), kpi_info_detail.period_type, delta_periods)
                    dict_context['date_from'] = start
                    dict_context['date_to'] = end

                    # change lines_dict of dict_context
                    dict_context['lines_dict'] = lines_dict

                    safe_eval(kpi_info_detail.code_compute, dict_context, mode="exec", nocopy=True)
                    value = dict_context.get('result', DEFAULT_SYMBOL)
                    if not value:
                        value = 0.0
                    data_kpi_usa_company_insight[user_id][kpi_info_detail.code_name] = {
                        'value': value,
                        'name': kpi_info_detail.name,
                        'type': kpi_info_detail.unit,
                        'period_type': dict(kpi_info_detail.periods_type).get(kpi_info_detail.period_type)
                    }
                record.kpi_usa_company_insight_value = str(data_kpi_usa_company_insight)
            else:
                record.kpi_usa_company_insight_value = False

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    def compute_kpis(self, company, user):
        """ Function help compute the kpi have check in the digest mail view and return the json is used
        to render in to template email

        :param company: is the company of user was working on that
        :param user:
        :return:
        """
        self.ensure_one()
        res = {}
        name = {}

        kpi_usa_value_dict = {}

        # Function _compute_timeframes return a dictionary contain detail range time of a period time
        # and the previous of it. it will return 3 kinds of type period is: lastmonth, lastweek, yesterday
        for tf_name, tf in self._compute_timeframes(company).items():

            # digest and previous_digest is the context of the digest with the default context value is
            # the difference range time, that is used to compute the kpi base on the compute function of that
            digest = self.with_context(start_date=tf[0][0], end_date=tf[0][1], company=company).sudo(user.id)
            previous_digest = self.with_context(start_date=tf[1][0], end_date=tf[1][1], company=company).sudo(user.id)
            kpis = {}
            for field_name, field in self._fields.items():
                if field.type == 'boolean' and field_name.startswith(('kpi_', 'x_kpi_', 'x_studio_kpi_')) and self[field_name]:
                    try:
                        if field_name.startswith("kpi_usa"):
                            field_name_value = kpi_usa_value_dict.setdefault(field_name, {})
                            if not field_name_value:
                                digest_kpi_usa = self.with_context(company=company, delta_periods=0).sudo(user.id)
                                previous_digest_kpi_usa = self.with_context(company=company, delta_periods=-1).sudo(user.id)
                                compute_value = digest_kpi_usa[field_name + '_value']
                                previous_value = previous_digest_kpi_usa[field_name + '_value']
                                field_name_value.update({
                                    'compute_value': compute_value,
                                    'previous_value': previous_value
                                })
                            else:
                                compute_value = field_name_value.get('compute_value')
                                previous_value = field_name_value.get('previous_value')
                        else:
                            compute_value = digest[field_name + '_value']
                            previous_value = previous_digest[field_name + '_value']
                    except AccessError:
                        # no access rights -> just skip that digest details from that user's digest email
                        continue

                    if self._fields[field_name + '_value'].type == 'char' and field_name.startswith("kpi_usa"):
                        compute_values = ast.literal_eval(compute_value)[user.id]
                        previous_values = ast.literal_eval(previous_value)[user.id]
                        name_kpi_usa = self.convert_to_name_module(field_name)
                        for key in compute_values.keys():
                            new_key = 'kpi_usa_' + key
                            gap = compute_values[key]['value'] - previous_values[key]['value']

                            value = convert_value_with_unit_type(compute_values[key]['type'],
                                                                 compute_values[key]['value'],
                                                                 self.sudo().company_id.currency_id)
                            margin = convert_value_with_unit_type(compute_values[key]['type'],
                                                                  gap,
                                                                  self.sudo().company_id.currency_id)
                            kpis.update({new_key: {
                                new_key: value,
                                'margin': margin,
                                'gap': gap,
                                'period_type': compute_values[key]['period_type'],
                                'field_name_parent': field_name
                            }})

                            name.update({new_key: compute_values[key]['name'] + ' (' + name_kpi_usa + ')'})

                    else:
                        margin = self._get_margin_value(compute_value, previous_value)
                        if self._fields[field_name + '_value'].type == 'monetary':
                            converted_amount = format_human_readable_amount(compute_value)
                            kpi_amount = self._format_currency_amount(converted_amount, company.currency_id)
                            kpis.update({field_name: {field_name: kpi_amount, 'margin': margin}})
                        else:
                            kpis.update({field_name: {field_name: compute_value, 'margin': margin}})
                        name.update({field_name: digest._fields[field_name].string})

                res.update({tf_name: kpis})
        kpi_order = sorted(res['yesterday'].keys())
        res.update({
            'name': name,
            'kpi_order': kpi_order
        })

        return res

    def compute_kpis_actions(self, company, user):
        res = super(Digest, self).compute_kpis_actions(company, user)
        dashboard = self.env.ref('account_dashboard.menu_account_dashboard').id
        res['kpi_usa_company_insight'] = 'account_dashboard.open_usa_journal_dashboard_kanban&menu_id={}'.format(dashboard)
        return res

    def convert_to_name_module(self, name_field):
        name_not_pre_fix = name_field.replace('kpi_usa_', '')
        name_module_no_underline = name_not_pre_fix.replace('_', ' ')
        upper_first_letter_name = name_module_no_underline.title()
        return upper_first_letter_name
