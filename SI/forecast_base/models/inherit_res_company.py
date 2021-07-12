# -*- coding: utf-8 -*-

import math
import numpy as np

from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models

from odoo.addons import decimal_precision as dp

from ..utils.config_utils import ForecastLevelLogicConfig
from odoo.addons.si_core.utils.datetime_utils import DEFAULT_DATE_FORMAT

from odoo.addons.resource.models.resource import float_to_time
from odoo.addons.si_core.utils.database_utils import query
from odoo.addons.si_core.utils.string_utils import PeriodType


class ResCompany(models.Model):
    _inherit = 'res.company'

    ###############################
    # CONSTANT
    ###############################
    TIME_SELECTION = [
        ('0', '12:00 PM'),
        ('1', '1:00 AM'),
        ('2', '2:00 AM'),
        ('3', '3:00 AM'),
        ('4', '4:00 AM'),
        ('5', '5:00 AM'),
        ('6', '6:00 AM'),
        ('7', '7:00 AM'),
        ('8', '8:00 AM'),
        ('9', '9:00 AM'),
        ('10', '10:00 AM'),
        ('11', '11:00 AM'),
        ('12', '12:00 AM'),
        ('13', '1:00 PM'),
        ('14', '2:00 PM'),
        ('15', '3:00 PM'),
        ('16', '4:00 PM'),
        ('17', '5:00 PM'),
        ('18', '6:00 PM'),
        ('19', '7:00 PM'),
        ('20', '8:00 PM'),
        ('21', '9:00 PM'),
        ('22', '10:00 PM'),
        ('23', '11:00 PM')
    ]

    ###############################
    # FIELDS
    ###############################
    sync_time_compute = fields.Selection(
        selection=TIME_SELECTION,
        string='Time Sync Data to Server',
        compute='_compute_sync_time_compute',
        help='Time Forecast Server will automatically crawl data and send forecast result'
    )

    sync_time_manual = fields.Selection(
        selection=TIME_SELECTION,
        string='Time Sync Data to Server (Manual)',
        compute='_compute_sync_time_manual',
        inverse='_inverse_sync_time_manual',
        help='Time Forecast Server will automatically crawl data and send forecast result'
    )

    sync_time = fields.Integer(store=True, required=True, default=1)

    auto_compute_sync_time = fields.Boolean(
        default=True,
        string='Automatically Compute Sync Time'
    )

    forecast_level_id = fields.Many2one('forecast.level.strategy',
                                        string='Forecast Level Strategy',
                                        required=True)
    forecast_level = fields.Char(string="Forecast Level",
                                 compute='_compute_forecast_level',
                                 search='_search_forecast_level')

    quotation_included = fields.Boolean(default=False)
    quotation_affect_days = fields.Integer(required=True, default=0,
                                           help="A quotation will be considered as a sales order if its creation "
                                                "date is within the previous \"Quotation Affect Days\" days from "
                                                "today's date.\n"
                                                "These special quotations will be summarized when the system runs the "
                                                "forecast engine.")
    quotation_affect_percentage = fields.Float(required=True, default=0.0,
                                               help="\"Quotation Affect Percentage\" determines what percentage of "
                                                    "ordered quantity in a special quotation will be treated as the "
                                                    "sales order quantity when running forecast.",
                                               digits=dp.get_precision('Adjust Percentage'))

    default_period_type = fields.Selection(PeriodType.LIST_PERIODS, default=PeriodType.MONTHLY_TYPE)

    ###############################
    # ONCHANGE FIELDS
    ###############################
    @api.onchange('sync_time_compute')
    def _onchange_auto_compute_sync_time(self):
        for company in self:
            if company.auto_compute_sync_time:
                sync_time = company.sync_time_compute
            else:
                sync_time = company.sync_time_manual
            company.write({'sync_time': sync_time})

    @api.onchange('quotation_included')
    def _onchange_quotation_included(self):
        if not self.quotation_included:
            self.quotation_affect_days = 0
            self.quotation_affect_percentage = 0
        else:
            self.quotation_affect_days = 90
            self.quotation_affect_percentage = 90

    @api.onchange('quotation_affect_percentage')
    def _onchange_quotation_affect_percentage(self):
        if self.quotation_affect_percentage > 100:
            self.quotation_affect_percentage = 100

        if self.quotation_affect_percentage < 0:
            self.quotation_affect_percentage = 0

    ###############################
    # COMPUTED FIELDS
    ###############################
    def _compute_forecast_level(self):
        for record in self:
            if not record.forecast_level:
                record.forecast_level = record.forecast_level_id.name

    @api.depends('sync_time')
    def _compute_sync_time_manual(self):
        for company in self:
            company.sync_time_manual = str(company.sync_time)

    def _compute_sync_time_compute(self):
        for company in self:
            free_hour = company.get_free_hour()
            user_tz = timezone(company.sudo().timezone or 'UTC')
            hour_by_tz = company._convert_to_tz_hour(free_hour, user_tz, UTC)
            values = {'sync_time_compute': str(hour_by_tz)}
            if company.auto_compute_sync_time:
                values.update({'sync_time': hour_by_tz})
                company.write(values)

    ###############################
    # INVERSE FIELDS
    ###############################
    def _inverse_sync_time_manual(self):
        for company in self:
            company.sync_time = int(company.sync_time_manual)

    def get_free_hour(self, number_of_past_date=100):
        """ Function get free hour, which the time user don't serve their customers,
         base on the data in the sale order table and the time customer order
         (date_order column)

        :param number_of_past_date:
        :return: Free Hour at UTC
        :rtype: float
        """
        self.ensure_one()
        query_clause = """
            SELECT  date_order, 
                    hour_order, 
                    count_order, 
                    rank() over (
                         PARTITION BY date_order
                         ORDER BY count_order) as rank
            FROM (
                SELECT date_part('hour', date_order) AS hour_order,
                       date_trunc('day', date_order) AS date_order,
                       count(*) AS count_order
                FROM sale_order
                WHERE company_id = %s 
                    AND date_order >= now() - %s * INTERVAL '1 day'
                GROUP BY date_part('hour', date_order), date_trunc('day', date_order)) temp
            """
        company_id = self.id or self._origin.id
        self._cr.execute(query_clause, (company_id, number_of_past_date))
        stats_pick = {}
        for row in self._cr.fetchall():
            date_order = datetime.strftime(row[0], DEFAULT_DATE_FORMAT)
            stats_pick.setdefault(date_order, [0]*24)[int(row[1])] = row[2]

        list_hours_ranking = [list(map(lambda x: x/max(value)*len(value), value)) for key, value in stats_pick.items()]
        list_hour_np = np.array(list_hours_ranking)
        hour_sync_data = 0.0
        if len(list_hour_np):
            order_hour = list(np.average(list_hour_np, axis=0))

            hour_sync_data = self._get_free_hour(order_hour)
        return hour_sync_data

    ###############################
    # SEARCH FUNCTIONS
    ###############################
    def _search_forecast_level(self, operator, value):
        return [('forecast_level_id.name', operator, value)]

    ###############################
    # PRIVATE FUNCTIONS
    ###############################
    def _get_free_hour(self, picks):
        """

        :param picks:
        :type picks: list
        :return:
        :rtype: float
        """
        rm_zero = list(map(lambda x: x+1, picks))
        stamps = [i for i, x in enumerate(rm_zero) if x == min(rm_zero)]
        list_ranges = []
        min_index = 0
        max_index = len(rm_zero) - 1

        for stamp in stamps:
            stamp_info = {}
            # dec
            dec_index = stamp
            while True:
                index = dec_index - 1
                if index < min_index:
                    index = max_index
                if index == stamp:
                    break
                if abs(rm_zero[index] / (rm_zero[stamp] or 1) - 1) * 100 > 5:
                    break
                dec_index = index
            # inc
            inc_index = stamp
            while True:
                index = inc_index + 1
                if index > max_index:
                    index = min_index
                if dec_index == index:
                    break
                if abs(rm_zero[index] / (rm_zero[stamp] or 1) - 1) * 100 > 5:
                    break
                inc_index = index

            stamp_info.update({
                'stamp': stamp,
                'start': dec_index,
                'end': inc_index,
            })
            list_ranges.append(stamp_info)

        start = -1
        end = -1
        distance = 0
        for stamp in list_ranges:
            local_dist = self._compute_distance_time(stamp['start'], stamp['end'], len(rm_zero))
            if start == -1 or distance != local_dist:
                distance = local_dist
                start = stamp['start']
                end = stamp['end']
        return self._choose_hour(start, end, len(rm_zero))

    @staticmethod
    def _compute_distance_time(start, end, length):
        distance = end - start
        if distance < 0:
            distance = length + distance
        return distance + 1

    def _choose_hour(self, start, end, length):
        """ The function compute the best option in range start time to end time.

        :param start:
        :param end:
        :param length:
        :return:
        :rtype: float
        """
        distance = self._compute_distance_time(start, end, length)
        hour = start + distance / 2
        if hour > length - 1:
            hour -= (length - 1)
        return math.floor(hour)

    @staticmethod
    def _convert_to_tz_hour(hour, tz_from, tz_to):
        """

        :param tz_to:
        :type tz_to: class<timezone>
        :param tz_from:
        :type tz_from: class<timezone>
        :param hour:
        :type hour: float
        :return:
        :rtype: float
        """
        time_hour = float_to_time(hour)
        utc_hour = tz_from.localize(datetime.combine(datetime.now(), time_hour)).astimezone(
            tz_to).replace(tzinfo=None).hour
        return utc_hour

    ###############################
    # GET FUNCTIONS
    ###############################
    def get_forecast_object_records(self, domain, order_by, limit, **kwargs):
        """
        Function to crawl forecast object info of company
        :param domain:
        :param order_by:
        :param limit:
        :return:
        :rtype: list(dict)
        """
        records = []

        company_env = self.env['res.company'].sudo()
        company_ids = company_env.search(domain, limit=limit, order=order_by)
        for company in company_ids:
            records.append({
                'company_id': company.id,
                'summarize_source': company.summarize_source,
                'summarize_time_field': company.summarize_time_field,
                'state_affect': company.state_affect
            })

    def get_company_config_records(self, domain, order_by, limit, **kwargs):
        """
        Function to crawl configuration info of company
        :param domain:
        :param order_by:
        :param limit:
        :return:
        :rtype: list(dict)
        """
        records = []
        company_env = self.env['res.company'].sudo()
        company_ids = company_env.search(domain, limit=limit, order=order_by)

        forecast_level_by_company = company_env.get_forecast_level_by_company(company_ids.ids)

        for company in company_ids:
            company_id = company.id
            records += [{
                'forecast_level': forecast_level_by_company.get(company_id),
                'company_id': company_id,
                'create_date': datetime.now(),
                'write_date': datetime.now(),
                'summarize_source': company.summarize_source,
                'summarize_time_field': company.summarize_time_field,
                'state_affect': company.state_affect
            }]

        return records

    def get_company_records(self, domain, order_by, limit, **kwargs):
        """
        Function to crawl configuration info of company
        :param domain:
        :param order_by:
        :param limit:
        :return:
        :rtype: list(dict)
        """
        records = []
        company_env = self.env['res.company'].sudo()
        company_ids = company_env.search(domain, limit=limit, order=order_by)

        forecast_level_by_company = company_env.get_forecast_level_by_company(company_ids.ids)

        for company in company_ids:
            company_id = company.id
            records += [{
                'forecast_level': forecast_level_by_company.get(company_id),
                'id': company_id,
                'name': company.name,
                'timezone': company.timezone,
                'parent_id': company.parent_id.id or None,
                'partner_id': company.partner_id.id,
                'create_date': datetime.now(),
                'write_date': datetime.now(),
                'summarize_source': company.summarize_source,
                'summarize_time_field': company.summarize_time_field,
                'state_affect': company.state_affect
            }]

        return records

    def get_company_records_origin(self, domain, order_by, limit):
        """ Function return when  crawl basic information of company

        :param domain:
        :param order_by:
        :param limit:
        :return:
        :rtype: list(dict)
        """
        companies = query(cr=self.env.cr,
                          table_name=self._inherit,
                          selected_fields='id, name, parent_id, partner_id, create_date, write_date',
                          domain=domain,
                          order=order_by,
                          limit=limit)

        company_ids = [company['id'] for company in companies]

        forecast_level_by_company = self.get_forecast_level_by_company(company_ids)

        for company in companies:
            company['forecast_level'] = forecast_level_by_company.get(company['id'])

        return companies

    def get_forecast_level_by_company(self, company_ids):
        """ Get the forecast level for each company and return as a dict

        :param company_ids:
        :type company_ids: list(int)
        :return:
        :rtype: dict
        """

        forecast_level_by_company = dict(self.env['res.company'].search(
            [('id', 'in', company_ids)]).mapped(lambda c: (c.id, c.forecast_level)))
        return forecast_level_by_company

    def get_companies_sync_hour(self):
        """ Function return when the time to run sync data for each companies

        :return list[dict]:
        Ex: {
                'company_id': company.id,
                'sync_hour': utc_sync_time
            }
        """
        companies = self.search([]).sudo()
        companies_info = []
        for company in companies:
            if company.auto_compute_sync_time:
                sync_time = company.sync_time_compute
            else:
                sync_time = company.sync_time_manual

            user_tz = timezone(company.timezone or 'UTC')
            utc_sync_time = self._convert_to_tz_hour(int(sync_time), user_tz, UTC)
            companies_info.append({
                'company_id': company.id,
                'sync_hour': utc_sync_time
            })

        return companies_info

    def get_so_state_affect_percentage_dict(self, company):
        """

        :param company:
        :return:
        :rtype: dict
        """
        result = {
            'draft': {'affect_days': company.quotation_affect_days, 'affect_percentage': company.quotation_affect_percentage},
            'sent': {'affect_days': company.quotation_affect_days, 'affect_percentage': company.quotation_affect_percentage},
            'sale': {'affect_days': -1, 'affect_percentage': 100},
            'done': {'affect_days': -1, 'affect_percentage': 100},
            'cancel': {'affect_days': 0, 'affect_percentage': 0},
        }
        return result

    @api.model
    def action_close_prep_announcement_onboarding(self):
        """ Mark the prep announcement onboarding panel as closed. """
        self.env.user.company_id.prep_announcement_onboarding_state = 'closed'

    def get_forecast_level_by_company_id(self, company_ids=None):
        """
        Get forecast level of each company
        :param company_ids: list of company id
        :type company_ids: Union[List[int], None]
        :return: a dict with the key is company_id and the value is forecast level of this company
        :rtype: dict
        """
        domain = []
        if company_ids:
            domain.append(('id', 'in', company_ids))
        result = {}
        records = self.sudo().search(domain)
        for record in records:
            company_id = record.id
            result.setdefault(company_id, ForecastLevelLogicConfig.WAREHOUSE_LEVEL)
            result[company_id] = record.forecast_level_id

        return result

    ###############################
    # INIT FUNCTIONS
    ###############################
    @api.model
    def init_forecast_level(self):
        company_ids = self.sudo().search([])
        warehouse_forecast_level = self.env.ref('forecast_base.forecast_warehouse_level')
        company_ids.write({
            'forecast_level_id': warehouse_forecast_level.id
        })
