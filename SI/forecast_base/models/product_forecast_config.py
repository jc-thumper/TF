# -*- coding: utf-8 -*-

import json
import logging
import math

import requests

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from odoo.addons.queue_job.job import job

from odoo.addons.queue_job.exception import RetryableJobError

from odoo.addons.base.models.res_lang import DEFAULT_DATE_FORMAT
from odoo.addons.si_core.utils.request_utils import ServerAPIv1, ServerAPICode
from odoo.addons.si_core.utils import datetime_utils
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.addons.si_core.utils.database_utils import query

from datetime import datetime, date, timedelta

_logger = logging.getLogger(__name__)

DATETIME = fields.Datetime()


class DateTimeEncoder(json.JSONEncoder):
    def default(self, value):
        if isinstance(value, datetime):
            result = datetime_utils.convert_tz_to_utc(value).isoformat(sep='T')
        elif isinstance(value, date):
            datetime_value = datetime.combine(value, datetime.min.time())
            result = datetime_utils.convert_tz_to_utc(datetime_value).isoformat()
        else:
            result = json.JSONEncoder.default(self, value)
        return result


class ProductForecastConfig(models.Model):
    _name = "product.forecast.config"
    _inherit = 'abstract.product.info'
    _description = "Product Forecast Configuration"

    ###############################
    # HELPER METHOD
    ###############################
    @api.model
    def get_frequency(self):
        if self.auto_update:
            frequency = self.product_clsf_info_id.forecast_group_id.frequency
        else:
            frequency = self.frequency
        return frequency

    @api.constrains('next_call')
    def _check_next_call(self):
        """
        Check if selected time is past time
        :return:
        :raise: ValidationError if past time is selected
        """
        for config in self:
            if config.next_call is not False and config.next_call <= datetime.now().date():
                raise ValidationError(_('%s is invalid. Can not select past time', config.next_call))

    def get_selected_field(self):
        return ['id', 'product_id', 'company_id', 'warehouse_id', 'period_type_custom',
                'no_periods_custom', 'frequency_custom', 'auto_update', 'create_date', 'next_call',
                'write_date']

    def get_prod_fore_conf_records(self, domain, order_by, limit):
        """
        Get information of product forecast configuration
        """
        selected_fields = self.get_selected_field()
        prod_fore_conf = query(cr=self.env.cr,
                               table_name=self._name,
                               selected_fields=','.join(selected_fields),
                               domain=domain,
                               order_by=order_by,
                               limit=limit)

        return prod_fore_conf

    ###############################
    # FIELDS
    ###############################
    __auto_update_config = True
    _rec_name = 'warehouse_id'
    product_clsf_info_id = fields.Many2one('product.classification.info')

    forecast_group_id = fields.Many2one('forecast.group',
                                        related='product_clsf_info_id.forecast_group_id',
                                        string='Forecast Group')

    period_type = fields.Selection(PeriodType.LIST_PERIODS, required=True,
                                   compute='_compute_forecasting_configuration',
                                   inverse='_inverse_forecast_configuration',
                                   search='_search_period_type')
    no_periods = fields.Integer(required=True, string='Number of Periods',
                                compute='_compute_forecasting_configuration',
                                inverse='_inverse_forecast_configuration',
                                search='_search_no_periods')
    frequency = fields.Selection(string='Frequency', selection=PeriodType.ORDERED_FORECASTING_FREQUENCY,
                                 default=PeriodType.WEEKLY_TYPE, required=True,
                                 compute='_compute_forecasting_configuration',
                                 inverse='_inverse_forecast_configuration',
                                 search='_search_frequency')

    next_call = fields.Date('Next Execution Date')
    period_type_custom = fields.Selection(PeriodType.LIST_PERIODS, required=True,
                                          help="Technical field: store the value of period type changed by the user.")

    period_type_origin = fields.Selection(PeriodType.LIST_PERIODS, store=True, readonly=True,
                                          help="Technical field: store forecasting type sent from the SI server."
                                               "Don't edit this field in your code.")

    no_periods_custom = fields.Integer(required=True)
    frequency_custom = fields.Selection(PeriodType.ORDERED_FORECASTING_FREQUENCY, required=True)

    auto_update = fields.Boolean(required=True, string='Auto Update', default=True)
    active = fields.Boolean(required=True, default=True)
    procurement_cycle = fields.Integer(string='Procurement Cycle', default=10)

    has_forecasted = fields.Boolean(compute='_compute_has_forecasted',
                                    search='_search_has_forecasted')

    forecast_adjust_id = fields.Many2one('forecast.result.adjust')

    _sql_constraints = [
        ('pcw_uid_unique', 'unique (product_id, company_id, warehouse_id)', 'Product Information must be unique'),
    ]

    ###############################
    # ONCHANGE FUNCTIONS
    ###############################

    @api.onchange('auto_update')
    def _onchange_auto_update(self):
        """
        Switch to using custom forecast configuration when auto update is false,
        otherwise forecast group configuration of used
        :return:
        """
        self.ensure_one()
        if self.auto_update:
            self.period_type = self.forecast_group_id.period_type
            self.no_periods = self.forecast_group_id.no_periods
            self.frequency = self.forecast_group_id.frequency
        else:
            self.period_type = self.period_type_custom
            self.no_periods = self.no_periods_custom
            self.frequency = self.frequency_custom

    @api.onchange('period_type',
                  'no_periods',
                  'frequency',
                  'next_call')
    def _onchange_config(self):
        """
        Ensuring the product's forecast configuration is the same as the custom config, we need the custom config fields
        for assignment when `auto_update` is true
        :return:
        :raise: ValidationError if past time is selected
        """
        self.ensure_one()
        self.period_type_custom = self.period_type
        self.no_periods_custom = self.no_periods
        self.frequency_custom = self.frequency
        if self.next_call is not False and self.next_call <= datetime.now().date():
            raise ValidationError(_('%s is invalid. Can not select past time', self.next_call))

    @api.onchange('frequency', 'period_type')
    def _onchange_frequency_and_period_type(self):
        self.ensure_one()
        # self._check_next_call_value()

    @api.onchange('next_call')
    def _onchange_next_call(self):
        self._check_frequency_value()

    ###############################
    # COMPUTE FUNCTIONS
    ###############################
    @api.depends('product_id', 'warehouse_id', 'company_id', 'period_type')
    def _compute_has_forecasted(self):
        for conf in self:
            has_forecasted = False
            forecast_result_adjust_line_ids = self.env['forecast.result.adjust.line'].search([
                ('product_id', '=', conf.product_id.id),
                ('warehouse_id', '=', conf.warehouse_id.id),
                ('company_id', '=', conf.company_id.id),
                ('period_type', '=', conf.period_type_origin),
            ])
            if forecast_result_adjust_line_ids:
                for line in forecast_result_adjust_line_ids:
                    if line.forecast_line_id:
                        has_forecasted = True
                        break

            conf.has_forecasted = has_forecasted

    @api.depends('forecast_group_id',
                 'forecast_group_id.period_type',
                 'forecast_group_id.no_periods',
                 'forecast_group_id.frequency')
    def _compute_forecasting_configuration(self):
        """
        Compute the forecasting configuration of the product, the configuration
        will use custom config when `auto_update` field is false and forecast
        group config is used when `auto_update` is true
        :return:
        """
        for product in self:
            if product.auto_update:
                forecast_group_id = product.forecast_group_id
                product.period_type = forecast_group_id.period_type
                product.no_periods = forecast_group_id.no_periods
                product.frequency = forecast_group_id.frequency

                product.period_type_custom = forecast_group_id.period_type
                product.no_periods_custom = forecast_group_id.no_periods
                product.frequency_custom = forecast_group_id.frequency
            else:
                product.period_type = product.period_type_custom
                product.no_periods = product.no_periods_custom
                product.frequency = product.frequency_custom

    @api.depends('product_clsf_info_id',
                 'product_clsf_info_id.forecast_group_id')
    def _compute_forecast_group_id(self):
        for product in self:
            product_clsf_id = self.env['product.classification.info'] \
                .get_product_info(product.product_id.id, product.company_id.id,
                                  product.warehouse_id.id)
            product.forecast_group_id = product_clsf_id.forecast_group_id

    ###############################
    # INVERSE FUNCTIONS
    ###############################
    def _inverse_forecast_configuration(self):
        """
        Ensuring the product's forecast configuration is the same as the custom config,
        we need the custom config fields
        for assignment when `auto_update` is true
        :return:
        """
        for config in self:
            config.period_type_custom = config.period_type
            config.no_periods_custom = config.no_periods
            config.frequency_custom = config.frequency

    ###############################
    # SEARCH FUNCTIONS
    ###############################
    def _search_period_type(self, operator, value):
        if self.auto_update:
            return [('forecast_group_id.period_type', operator, value)]
        else:
            return [('period_type_custom', operator, value)]

    def _search_no_periods(self, operator, value):
        if self.auto_update:
            return [('forecast_group_id.no_periods', operator, value)]
        else:
            return [('no_periods_custom', operator, value)]

    def _search_frequency(self, operator, value):
        if self.auto_update:
            return [('forecast_group_id.frequency', operator, value)]
        else:
            return [('frequency_custom', operator, value)]

    def _search_has_forecasted(self, operator, value):
        if operator not in ('=', '!='):
            raise ValueError('Invalid operator: %s' % (operator,))

        forecast_result_adjust_ids = self.env['forecast.result.adjust'].search([
            ('has_forecasted', operator, value)
        ])
        configs_have_forecasted = self
        for forecast_res in forecast_result_adjust_ids:
            configs_have_forecasted += self.search([
                ('product_id', '=', forecast_res.product_id.id),
                ('company_id', '=', forecast_res.company_id.id),
                ('warehouse_id', '=', forecast_res.warehouse_id.id)
            ])
        operator = 'in' if (operator == '=' and value) or (operator == '!=' and not value) else 'not in'
        return [('id', operator, configs_have_forecasted.ids)]

    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_comp_config_data(self, products_info, update_active=False):
        """

        :param products_info:
        :type products_info: list[dict]
        :param update_active:
        :return:
        """
        try:
            _logger.info("Update product forecast config with data: %s", products_info)
            updated_conf_ids = []
            company_effected = []

            conf_obj = self
            prod_clsf_env = self.env['product.classification.info']

            # Step 1: active config of all product in ``products_info``
            for prod_info in products_info:
                company_id = prod_info.get('company_id')
                if company_id and company_id not in company_effected:
                    company_effected.append(company_id)

                product_domain = self._get_domain_product_forecast_config(prod_info)
                config_info = self.get_product_forecast_config(product_domain)

                product_clsf_info_id = prod_clsf_env.get_product_clsf_info(product_domain)
                if config_info:
                    # Step 1.1: update config have been existed
                    updated_conf_ids.append(config_info.id)
                    self._set_auto_update_config(False)

                    # Just write when have a update
                    write_content = {}
                    if config_info.product_clsf_info_id.id != product_clsf_info_id.id:
                        write_content.update({
                            'product_clsf_info_id': product_clsf_info_id.id,
                        })
                    if not config_info.active:
                        write_content.update({'active': True})

                    if write_content:
                        config_info.sudo().with_context(auto_update_config=False).write(write_content)
                        config_info._inverse_forecast_configuration()
                        conf_obj += config_info
                elif product_clsf_info_id and product_clsf_info_id.forecast_group_id:
                    # Step 1.2: create new config
                    self._set_auto_update_config(False)
                    fore_group = product_clsf_info_id.forecast_group_id

                    config_data = self._gen_product_forecast_config_data(prod_info, fore_group, product_clsf_info_id)
                    new_config = self.sudo().with_context(auto_update_config=False).create(config_data)
                    self.env.cr.commit()
                    updated_conf_ids.append(new_config.id)
                    new_config._inverse_forecast_configuration()
                    conf_obj += new_config

        except Exception as e:
            _logger.exception("Function update_comp_config_data have some exception: %s" % e)
            raise RetryableJobError('Must be retried later')

    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_execute_date(self, fore_result_adjust_ids,
                            execute_date=datetime.now()):
        """

        :param fore_result_adjust_ids:
        :param execute_date:
        :return:
        """
        try:
            fore_adjust_ids = self.env['forecast.result.adjust'] \
                .search([('id', 'in', fore_result_adjust_ids)])

            for fore_adjust in fore_adjust_ids:
                # get the frequency to compute Next Execution Date
                config_id = self.search([('product_id', '=', fore_adjust.product_id.id),
                                         ('company_id', '=', fore_adjust.company_id.id),
                                         ('warehouse_id', '=', fore_adjust.warehouse_id.id)], limit=1)
                if config_id:
                    next_call = execute_date + datetime_utils.get_delta_time(config_id.get_frequency(), no_periods=1)
                    period_type = config_id.forecast_group_id.period_type \
                        if config_id.auto_update \
                        else config_id.period_type_custom
                    print(next_call, period_type, config_id.get_frequency(), execute_date)
                    config_id.write({
                        'next_call': datetime_utils.convert_from_datetime_to_str_date(next_call),
                        'forecast_adjust_id': fore_adjust.id,
                        'period_type': period_type
                    })

        except Exception as e:
            _logger.exception("Function update_execute_date have some exception: %s" % e)
            raise RetryableJobError('Must be retried later')

    ###############################
    # GENERAL FUNCTIONS
    ###############################
    @api.model
    def create(self, vals):
        self._check_frequency_value(vals)
        # self._check_next_call_value(vals)
        product_clsf_info_id = vals.get('product_clsf_info_id')
        if product_clsf_info_id:
            prod_clsf_info = self.env['product.classification.info'] \
                .search([('id', '=', product_clsf_info_id)], limit=1)
            fore_group = prod_clsf_info.forecast_group_id

            vals.setdefault('frequency_custom', fore_group.frequency)
            vals.setdefault('period_type_custom', fore_group.period_type)
            vals.setdefault('no_periods_custom', fore_group.no_periods)

        res = super(ProductForecastConfig, self).create(vals)
        return res

    def write(self, vals):
        self._check_frequency_value(vals)
        # self._check_next_call_value(vals)
        res = super(ProductForecastConfig, self).write(vals)
        return res

    def check_status_of_product_forecast_config(self, data_info):
        """
        Check product forecast config is updated in the Odoo database or not
        :param data_info: info to check
        :type data_info: list[dict]
        [
            {
                "company_id": 1,
                "status": True,
                "product_clsf_info_ids": []
            },
            {
                "company_id": 2,
                "status": True,
                "product_clsf_info_ids": []
            }
        ]
        :return: a list of dict
        [
            {
                "company_id": 1,
                "status": True
            },
            {
                "company_id": 2,
                "status": True
            }
        ]
        """
        result = []
        # the status of the final step is always True, the result of this step will be sent to FE server
        is_continue = True
        try:
            for item in data_info:
                company_id = item.get('company_id')
                company_status = item.get('status')
                product_clsf_info_ids = item.get('product_clsf_info_ids')

                if company_status is False:
                    _logger.info("Odoo client is still processing product classification info for company_id = %d."
                                 % company_id)
                    result.append({
                        "company_id": company_id,
                        "status": False
                    })
                else:

                    sql_query = """
                        SELECT count(*) as total_row
                        FROM product_forecast_config
                        WHERE product_clsf_info_id IN %s AND active = True;
                    """
                    sql_param = [tuple(product_clsf_info_ids)]
                    self.env.cr.execute(sql_query, sql_param)

                    records = self.env.cr.dictfetchall()
                    actual_n_records = records[0].get('total_row', 0) if records else 0
                    result.append({
                        "company_id": company_id,
                        "status": actual_n_records == len(product_clsf_info_ids)
                    })

        except Exception:
            _logger.exception("An exception when check status of update classification info process.", exc_info=True)
            raise
        return result, is_continue

    def get_product_forecast_config(self, product_domain):
        config_info = None
        try:
            config_info = self.with_context(active_test=False).sudo().search(product_domain, limit=1)
        except (Exception, ):
            _logger.warning('Having some errors when get product forecast configuration', exc_info=True)
        return config_info

    ###############################
    # PRIVATE FUNCTIONS
    ###############################
    def _get_domain_product_forecast_config(self, prod_info):
        """

        :param prod_info:
        :return:
        """
        domain = []
        try:
            cid = prod_info['company_id']
            company_id = self.env['res.company'].search([('id', '=', cid)])
            if company_id:
                forecast_level_id = company_id.forecast_level_id
                keys = forecast_level_id.get_list_of_extend_keys()
                for key in keys:
                    domain.append((key, '=', prod_info.get(key)))
        except (Exception,):
            _logger.warning('Having some errors when get product forecast configuration domain',
                            exc_info=True)
        return domain

    def _gen_product_forecast_config_data(self, prod_info, fore_group, product_clsf_info_id):
        """ Function generate Product forecast configuration data used to update to table product_forecast_config

        :param dict prod_info:
        Ex: {
                'product_id': 1234,
                'company_id': 1,
                'warehouse_id': 2
            }
        :param ForecastGroup fore_group:
        :param ProductClassificationInfo product_clsf_info_id:
        :return:
        """
        config_data = {}
        try:
            cid = prod_info['company_id']
            company_id = self.env['res.company'].search([('id', '=', cid)])
            if company_id:
                # initial product forecast config data
                default_forecasting_type = self.env['forecast.item'].get_forecasting_type(prod_info)
                period_type = default_forecasting_type or fore_group.period_type
                frequency = default_forecasting_type or fore_group.frequency
                no_periods = PeriodType.PERIODS_TO_FORECAST.get(default_forecasting_type, fore_group.no_periods)

                config_data = {
                    'product_id': prod_info.get('product_id'),
                    'company_id': prod_info.get('company_id'),
                    # 'warehouse_id': prod_info.get('warehouse_id'),
                    'active': True,
                    'auto_update': False if default_forecasting_type else True,
                    'product_clsf_info_id': product_clsf_info_id.id,
                    'period_type_custom': period_type,
                    'period_type_origin': period_type,
                    'no_periods_custom': no_periods,
                    'frequency_custom': frequency
                }

                # initial key data used to update to product forecast config
                forecast_level_id = company_id.forecast_level_id
                pfc_keys = forecast_level_id.get_list_of_extend_keys()
                key_config = dict([(k, prod_info.get(k)) for k in pfc_keys])

                # update to config data
                config_data.update(key_config)
        except (Exception,):
            _logger.warning('Having some errors when get product forecast configuration domain',
                            exc_info=True)
        return config_data

    def _check_frequency_value(self, vals=None):
        vals = vals or {}
        for config in self:
            period_type = vals.get('period_type', config.period_type)
            frequency = vals.get('frequency', config.frequency)
            max_idx = PeriodType.FORECASTING_FREQUENCY_RANK.get(period_type, 1)
            current_idx = PeriodType.FORECASTING_FREQUENCY_RANK.get(frequency)
            if max_idx and current_idx and current_idx > max_idx:
                allow_frequency = list(map(lambda l: l[0],
                                           filter(lambda l: l[1] <= max_idx,
                                                  list(PeriodType.FORECASTING_FREQUENCY_RANK.items()))))
                raise ValidationError(_('The value for the field Forecasting Frequency should be %s.',
                                        ', '.join(allow_frequency)))

    def _check_next_call_value(self, vals=None):
        """ Function check some constrains value of the next_call, if it exist in vals

        :param dict vals: create/write data of product_forecast_config table
        :return:
        """
        vals = vals or {}
        next_call = vals.get('next_call')
        if next_call:
            for config in self:
                product = config.product_id
                warehouse = config.warehouse_id

                product_name = product.name_get()[0][1] if product else ''
                warehouse_name = warehouse.name_get()[0][1] if warehouse else ''

                forecast_adjust_id = config.forecast_adjust_id
                if forecast_adjust_id:
                    last_receive_result = forecast_adjust_id.last_receive_result
                    if last_receive_result:
                        gap_dates = (datetime.strptime(next_call, DEFAULT_SERVER_DATE_FORMAT).date()
                                     - last_receive_result).days
                        period_size = PeriodType.PERIOD_SIZE.get(config.period_type, 7)
                        min_available_gap = 0.2 * period_size
                        max_available_gap = 2 * period_size
                        print(min_available_gap, max_available_gap, gap_dates, next_call, last_receive_result)
                        if gap_dates < min_available_gap:
                            available_date = last_receive_result + timedelta(days=math.ceil(min_available_gap))
                            raise ValidationError(_('The Next Execution Date of product %s '
                                                    'in warehouse "%s" current is next %s day(s), should be after %s.' %
                                                    (product_name, warehouse_name, gap_dates,
                                                     available_date.strftime(DEFAULT_DATE_FORMAT),)
                                                    ))

                        if gap_dates > max_available_gap:
                            available_date = last_receive_result + timedelta(days=math.ceil(max_available_gap))
                            raise ValidationError(_('The Next Execution Date of product %s '
                                                    'in warehouse "%s" current is next %s day(s), '
                                                    'it should be before %s.' %
                                                    (product_name, warehouse_name, gap_dates,
                                                     available_date.strftime(DEFAULT_DATE_FORMAT), )
                                                    ))

    def _is_auto_update_config(self):
        auto_update = True
        if not self.__auto_update_config:
            self.__auto_update_config = True
            auto_update = False
        return auto_update

    def _set_auto_update_config(self, auto_update):
        self.__auto_update_config = auto_update

    def _update_prod_fore_config_to_fe(self):
        auth_content = self.sudo().env['forecasting.config.settings'].get_auth_content()
        if auth_content:
            request_info = auth_content
            config_info = []
            for config in self:
                config_info.append({
                    'product_id': config.product_id.id,
                    'company_id': config.company_id.id,
                    'warehouse_id': config.warehouse_id.id,
                    'period_type': config.period_type,
                    'no_periods': config.no_periods,
                    'frequency': config.frequency,
                    'auto_update': config.auto_update,
                    'created_at': config.create_date,
                    'updated_at': config.write_date
                })
            if len(config_info):
                request_info.update({'data': config_info})
                try:
                    self._post_prod_fore_config(request_info)
                except Exception as e:
                    _logger.exception('Exception in Update product forecast config to FE', exc_info=True)
                    raise e

    @classmethod
    def _post_prod_fore_config(cls, post_body):
        return cls._post_data_to_fe(post_body, ServerAPICode.UPDATE_PROD_CONF)

    @classmethod
    def _post_next_time_run(cls, post_body):
        return cls._post_data_to_fe(post_body, ServerAPICode.UPDATE_NEXT_TIME_RUN)

    @staticmethod
    def _post_data_to_fe(post_body, api_code):
        direct_order_url = ServerAPIv1.get_api_url(api_code)

        _logger.info("Call API to update product forecasting configuration to FE service")
        headers = {
            'Content-type': 'application/json'
        }
        return requests.post(direct_order_url, data=json.dumps(post_body, cls=DateTimeEncoder),
                             headers=headers, timeout=60)
