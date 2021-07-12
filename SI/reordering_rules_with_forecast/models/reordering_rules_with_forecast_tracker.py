# -*- coding: utf-8 -*-

import copy
import json
import logging
import math
import psycopg2
import requests

from datetime import datetime
from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError
from time import time
from operator import itemgetter

from .inherit_res_company import ResCompany
from odoo import models, fields, api
from odoo.addons import decimal_precision as dp

from odoo.addons.si_core.models.tracker_model import TrackerModel
from odoo.addons.si_core.utils import datetime_utils, request_utils
from odoo.addons.si_core.utils.database_utils import get_db_cur_time, append_log_access_fields_to_data
from odoo.addons.si_core.utils.request_utils import ExtraFieldType, ServerAPIv1, ServerAPICode, DOMAIN_SERVER_SI, \
    get_key_value_in_dict
from odoo.addons.si_core.utils.response_message_utils import HTTP_400_BAD_REQUEST, create_response_message
from odoo.addons.si_core.utils.string_utils import PeriodType, ServiceLevel, get_table_name

_logger = logging.getLogger(__name__)


class ReorderingRulesWithForecastTracker(models.Model, TrackerModel):
    """
    Object manage the tracker table in the database
    """
    _name = "reordering.rules.with.forecast.tracker"
    _monitor_model = "reordering.rules.with.forecast"
    _threshold = 1000
    _active_queue_job = False
    _abstract = False
    _auto = True

    ###############################
    # MODEL FIELDS
    ###############################
    new_safety_stock_forecast = fields.Float(
        'Safety Stock with Forecast value', digits=dp.get_precision('Product Unit of Measure'),
        store=True, readonly=True,
        help="Store the result from server. It is used to reset new safety stock quantity to original value ",
        default=0)
    new_min_forecast = fields.Float(
        'Minimum Quantity with Forecast value', digits=dp.get_precision('Product Unit of Measure'),
        store=True, readonly=True,
        help="Store the result from server. It is used to reset new min/max quantity to original value ", default=10)
    new_max_forecast = fields.Float(
        'Maximum Quantity with Forecast value', digits=dp.get_precision('Product Unit of Measure'),
        store=True,
        help="Store the result from server. It is used to reset new min/max quantity to original value", default=10)

    new_safety_stock = fields.Float(
        'Recommended Safety Stock', store=True, digits=dp.get_precision('Product Unit of Measure'),
        help="The value is copied from the field `new_safety_stock_forecast` and allow "
             "the user to update value in the UI",
        default=0)
    new_min_qty = fields.Float(
        'Recommended Min Quantity', store=True, digits=dp.get_precision('Product Unit of Measure'),
        help="The value is copied from the field `new_min_forecast` and allow the user to update value in the UI",
        default=0)
    new_max_qty = fields.Float(
        'Recommended Max Quantity ', store=True, digits=dp.get_precision('Product Unit of Measure'),
        help="The value is copied from the field `new_max_forecast` and allow the user to update value in the UI",
        default=0)

    product_id = fields.Many2one('product.product', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade')
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', required=False, ondelete="cascade")
    location_id = fields.Many2one('stock.location', 'Location', required=False, ondelete="cascade")
    master_product_id = fields.Many2one('product.product', required=False, ondelete='cascade')
    lot_stock_id = fields.Many2one('stock.location', required=False, ondelete='cascade')

    service_level_name = fields.Char(required=False)
    service_level = fields.Float(required=False)
    lead_times = fields.Char(required=False)
    summarize_data = fields.Char(required=False)
    demand_data = fields.Char(required=False)
    min_max_frequency = fields.Char(required=False)
    holding_cost = fields.Float(required=False)
    po_flat_cost = fields.Float(required=False)
    mo_flat_cost = fields.Float(required=False)
    route_code = fields.Integer(required=False)
    standard_price = fields.Float(required=False)
    eoq = fields.Float(required=False, default=0)

    lead_days = fields.Integer(
        'Lead Time (Days)', default=1,
        readonly=True,
        help='Max lead time of Vendors', store=True)

    ###############################
    # MODEL FUNCTIONS
    ###############################
    def get_json_required_fields(self, forecast_level, **kwargs):
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        # get required fields from forecast level
        required_fields_from_forecast_level = forecast_level_obj.get_required_fields()
        required_fields_of_models = [
            ('min_forecast', float, None),
            ('max_forecast', float, None),
            ('safety_stock', float, None),
            ('eoq', float, None),
            ('create_time', str, ExtraFieldType.DATETIME_FIELD_TYPE),
            ('pub_time', str, ExtraFieldType.DATETIME_FIELD_TYPE)
        ]
        return required_fields_from_forecast_level + required_fields_of_models

    def transform_json_data_request(self, list_data, **kwargs):
        cur_time = get_db_cur_time(self.env.cr)
        for datum in list_data:
            datum = append_log_access_fields_to_data(self, datum, current_time=cur_time)
            min_forecast = datum.pop('min_forecast')
            max_forecast = datum.pop('max_forecast')
            safety_stock = datum.pop('safety_stock')
            datum.update({
                'new_safety_stock_forecast': safety_stock,
                'new_safety_stock': safety_stock,
                'new_min_forecast': min_forecast,
                'new_min_qty': min_forecast,
                'new_max_forecast': max_forecast,
                'new_max_qty': max_forecast,
            })

        return list_data

    def get_conflict_fields(self, required_fields=None, forecast_level=None, **kwargs):
        """
        Override function
        Return fields in conflict clause of the table
        :return list[str]: a list of field name
        """
        result = ['create_time']
        if required_fields:
            result += required_fields

        curr_forecast_level = forecast_level or self.env.user.company_id.forecast_level
        forecast_level_strategy_obj = self.env['forecast.level.strategy']
        forecast_level_obj = forecast_level_strategy_obj.create_obj(forecast_level=curr_forecast_level)
        conflict_fields = forecast_level_obj.get_conflict_fields_for_rrwf_tracker()
        _logger.info("Conflict fields in get_conflict_fields in RRwF API: %s", conflict_fields)
        return conflict_fields

    def get_product_route_code(self, product, allow_manufacture):
        product.ensure_one()
        route_code = 0
        if product.purchase_ok:
            route_code |= 1
        if allow_manufacture and product.bom_ids != False:
            route_code |= 2

        return route_code

    @api.model
    def get_future_demand_data(self, product_keys, product_values, lead_days):
        """ get the daily forecast data in range is the lead time of product

        :param list[str] product_keys: ['product_id', 'company_id', 'warehouse_id']
        :param product_values:
        :param lead_days:
        :return:
        """
        demand_data = []
        # number of points to return
        rounded_lead_days = max(math.ceil(lead_days) * 1.5, 30)

        domain = [('date', '>=', datetime.now().date())]

        domain += [(key, '=', val) for key, val in zip(product_keys,
                                                       get_key_value_in_dict(product_values,
                                                                             product_keys))]
        forecasts = self.env['forecast.result.daily'].sudo().search_read(
            domain, ['daily_forecast_result'],
            order='date', limit=rounded_lead_days)
        if forecasts:
            demand_data = [item.get('daily_forecast_result') for item in forecasts]

        return demand_data

    @api.model
    def get_summarize_data(self, product_keys, product_values, from_date, period_type):
        """
        Get the nearest summarize data of products in product_keys
        :param list[str] product_keys: list of key value to find a product
        :param dict product_values: a dictionary store value corresponding with the key
        :param datetime from_date:
        :param str period_type:
        :return list[float]:
        """
        FRAL_model = self.env['forecast.result.adjust.line']

        start_date = from_date
        end_date = start_date
        if period_type == PeriodType.WEEKLY_TYPE:
            start_date = end_date - relativedelta(weeks=25)
        elif period_type == PeriodType.MONTHLY_TYPE:
            start_date = end_date - relativedelta(months=6)
        elif period_type == PeriodType.QUARTERLY_TYPE:
            start_date = end_date - relativedelta(months=3*6)

        assert start_date != end_date, "Start date cannot equal end date"

        domain = [('period_type', '=', period_type),
                  ('start_date', '>=', start_date),
                  ('end_date', '<', end_date)]

        domain += [(key, '=', val) for key, val in zip(product_keys,
                                                       get_key_value_in_dict(product_values,
                                                                             product_keys))]

        # search all data in table ``forecast.result.adjust.line`` associated with planning_type
        summarized_data_records = FRAL_model.with_context(prefetch_fields=False). \
            search_read(domain, ['id', 'demand', 'start_date'])

        result = datetime_utils.create_key(period_type, start_date, end_date)
        for record in summarized_data_records:
            key = datetime_utils.get_key_from_time(period_type, record.get('start_date'))
            result[key] = record.get('demand')
        return list(result.values())

    ###############################
    # PROTECTED FUNCTIONS
    ###############################

    def _get_service_level_dict(self, company_config=None):
        """ Function calculate service factor from the product's service level,
        if it is a product have just added and don't have service level, we default it with category A
        :param company_config: a configuration of company for Reordering Rule with Forecast
        :type company_config: dict

        :return dict:
        """
        # The category of product is default category A when it is new product
        current_company = self.env.user.company_id
        if company_config is None:
            company_config = current_company.get_company_configuration_for_rrwf(company_id=current_company.id)

        service_level_dict = {
            ServiceLevel.CATEGORY_A: company_config.get('service_level_a', ResCompany.SERVICE_FACTOR_A),
            ServiceLevel.CATEGORY_B: company_config.get('service_level_b', ResCompany.SERVICE_FACTOR_B),
            ServiceLevel.CATEGORY_C: company_config.get('service_level_c', ResCompany.SERVICE_FACTOR_C),
        }
        return service_level_dict

    def _get_product_supplier_infos_by_keys(self, product_ids):
        """
        Function get delay time of all vendors of each product in each company and warehouse.
        :param list[int] product_ids: a list of values corresponding with the key to get the data
        :return dict: a dictionary with the format:
        - The key is ``tuple_keys``. Ex: <product_id>
        - The value is the service level of this corresponding key
        """
        result = {}
        try:
            if product_ids:
                sql_query = """
                    SELECT
                        pp.id AS product_id,
                        pt.id AS product_tmpl_id,
                        ps.id AS product_supplier_id,
                        ps.delay
                    FROM product_product pp
                    LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    LEFT JOIN product_supplierinfo ps ON pt.id = ps.product_tmpl_id
                    WHERE pp.id IN %s;
                """
                sql_params = (tuple(product_ids),)
                self.env.cr.execute(sql_query, sql_params)

                records = self.env.cr.dictfetchall()
                for record in records:
                    delay = record.get('delay')
                    if delay is not None:
                        result.setdefault(record.get('product_id'), []).append(delay)

                IrConfig = self.env['ir.config_parameter'].sudo()
                allow_manufacture = IrConfig.get_param(
                    'reordering_rules_with_forecast.module_forecast_preparation_with_mrp', '0') == '1'

                if allow_manufacture:
                    sql_query = """
                                        SELECT
                                            pp.id AS product_id,
                                            pt.produce_delay AS produce_delay
                                        FROM product_product pp
                                            LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                                        WHERE pp.id IN %s;
                                    """
                    sql_params = (tuple(product_ids),)
                    self.env.cr.execute(sql_query, sql_params)

                    records = self.env.cr.dictfetchall()
                    for record in records:
                        delay = record.get('produce_delay')
                        if delay is not None:
                            result.setdefault(record.get('product_id'), []).append(delay)

            return result
        except Exception as e:
            _logger.exception("An exception occur in _get_product_supplier_infos_by_keys", exc_info=True)
            raise e

    def get_items_to_update_rrwf(self, company_id, warehouse_id):
        """
        Get the list of products to add in RRwF
        - Existing products in RRwF
        - New products in Forecast Result Daily

        :param int company_id:
        :param int warehouse_id:
        :return list[dict]: a list of dictionary
        [
            {
                'product_id': <int>,
                'warehouse_id': <int>,
                'company_id': <int>
            },
            ...
        ]
        """
        try:
            sql_query = """
                SELECT
                    DISTINCT frd.product_id, frd.warehouse_id, frd.company_id
                FROM reordering_rules_with_forecast rrwf
                FULL JOIN forecast_result_daily frd ON
                    rrwf.product_id = frd.product_id AND
                    rrwf.warehouse_id = frd.warehouse_id AND
                    rrwf.company_id = frd.company_id
                WHERE 
                    frd.company_id = %(company_id)s AND
                    frd.warehouse_id = %(warehouse_id)s;
            """
            sql_param = {
                'company_id': company_id,
                'warehouse_id': warehouse_id
            }
            self.env.cr.execute(sql_query, sql_param)
            result = self.env.cr.dictfetchall()
            return result
        except Exception as e:
            _logger.exception('Error when getting updated products for RRwF')
            raise e

    def _get_newest_rrwf_data(self):
        """
        Get newest data to compute Reordering Rule with Forecast (RRwF)
        - Keys for a product (product_id, warehouse_id, company_id)
        - Product info: route_code, standard_price, lead_times, summarize_data, demand_data, service_level,...
        - Config parameters for RRwF: min_max_frequency, holding_cost, po_flat_cost, mo_flat_cost
        - Log info: create_time
        :return list[dict]: a list of newest data
        Ex: [
                {
                    "product_id": 1,
                    "company_id": 1,
                    "warehouse_id": 1,
                    "service_level_name": "group_a",
                    "service_level": 0.98,
                    "lead_times": [1, 2, 4, 6, 8, 3, 3, 7],
                    "summarize_data": [4, 2, 4, 6, 77, 8, 3, 2],
                    "demand_data": [32, 3, 5, 78, 4, 2, 2],
                    "create_time": "2020-01-15 23:27:00",
                    "min_max_frequency": "weekly",
                    "holding_cost": 20.0,
                    "po_flat_cost": 1.0,
                    "mo_flat_cost": 1.0,
                    "route_code": 1,
                    "standard_price": 123.3
                }
            ]
        """
        Product = self.env['product.product']
        IrConfig = self.env['ir.config_parameter'].sudo()
        current_company = self.env.user.company_id
        company_id = current_company.id
        curr_forecast_level = current_company.forecast_level
        user_timezone = self.env.user.company_id.partner_id.tz or datetime_utils.DEFAULT_TIMEZONE
        forecast_level_strategy_obj = self.env['forecast.level.strategy'].search([('name', '=', curr_forecast_level)],
                                                                                 limit=1)
        forecast_level_obj = forecast_level_strategy_obj.get_object()
        current_time = get_db_cur_time(cr=self.env.cr, timezone=user_timezone)

        # Step 1: get param from the current company
        created_time = datetime_utils.convert_from_datetime_to_str_datetime(current_time)
        config_params = current_company.get_company_configuration_for_rrwf(company_id=company_id)
        allow_manufacture = IrConfig.get_param('reordering_rules_with_forecast.module_forecast_preparation_with_mrp',
                                               False) == '1'

        period_type = config_params.get('min_max_update_frequency')
        from_date, to_date = datetime_utils.get_start_end_date_value(current_time, period_type)
        service_level_dict = self._get_service_level_dict(company_config=config_params)

        # get unique keys for each product base on the forecast level
        # Ex: ['product_id', 'company_id', 'warehouse_id']
        product_keys = forecast_level_obj.get_product_keys()

        item_values = self.get_items_to_update_rrwf(company_id=company_id,
                                                    warehouse_id=current_company.default_warehouse.id)
        product_info_dict = {
            item.get('product_id'): item for item in item_values
        }

        product_service_level_infos_dict = forecast_level_obj.get_product_service_level_infos_by_keys(
            obj=self, model_name=self._name, tuple_keys=product_keys, tuple_values=item_values)

        # get product supplier infos
        product_ids = [item.get('product_id') for item in item_values]
        product_supplier_infos_dict = self._get_product_supplier_infos_by_keys(product_ids=product_ids)
        products = Product.search([('id', 'in', product_ids)])

        # get standard price
        products_dict = {product.id: product for product in products}
        product_forecast_config_dict = self.env['product.forecast.config'].get_product_forecast_config_dict(company_id)

        data = []
        for item in item_values:
            product_id = item['product_id']
            warehouse_id = item['warehouse_id']
            product = products_dict.get(product_id)
            if product:
                product_forecast_config = product_forecast_config_dict.get((product_id, company_id, warehouse_id))
                if product_forecast_config:
                    forecast_type = product_forecast_config.period_type
                    product_info = product_info_dict.get(product_id, {})
                    service_level_name = product_service_level_infos_dict.get(itemgetter(*product_keys)(product_info),
                                                                              ServiceLevel.CATEGORY_A)
                    service_level_default = service_level_dict[ServiceLevel.CATEGORY_A]
                    # convert the service level to percentage
                    service_level = service_level_dict.get(service_level_name, service_level_default) / 100.0

                    list_lead_times = product_supplier_infos_dict.get(product_id, [])
                    max_lead_date = max(list_lead_times) if list_lead_times else 0
                    demand_data = self.get_future_demand_data(product_keys, product_info, max_lead_date)

                    if demand_data:
                        route_code = self.get_product_route_code(product, allow_manufacture)
                        summarize_data = self.get_summarize_data(product_keys, product_info, from_date, forecast_type)
                        rule_data = {
                            'service_level_name': service_level_name,
                            'service_level': service_level,
                            'lead_times': list_lead_times,
                            'summarize_data': summarize_data,
                            'demand_data': demand_data,
                            'create_time': created_time,
                            'min_max_frequency': forecast_type,
                            'holding_cost': config_params.get('holding_cost_per_inventory_value'),
                            'po_flat_cost': config_params.get('flat_cost_per_po'),
                            'mo_flat_cost': config_params.get('flat_cost_per_mo'),
                            'route_code': route_code,
                            'standard_price': product.standard_price
                        }
                        # append keys into the data
                        rule_data.update(product_info)
                        data.append(rule_data)
        return data

    def _create_new_records(self, new_records):
        """
        Create a new version in Reordering Rules with Forecast Report Tracker table
        :param list[dict] new_records: a list of dict
        :return:
        """
        new_data = copy.deepcopy(new_records)
        n_records = len(new_data)
        try:
            # append log access fields
            log_access_fields = ['create_uid', 'create_date']
            parsed_data = [
                append_log_access_fields_to_data(self, record, log_access_fields)
                for record in new_data]

            # get insert fields from the data
            inserted_fields = list(parsed_data[0].keys())
            sql_query = """
                INSERT INTO reordering_rules_with_forecast_tracker (%s)
                VALUES (%s);
            """ % (
                ','.join(inserted_fields),
                ','.join(["%s"] * len(inserted_fields))
            )

            sql_params = [get_key_value_in_dict(item, inserted_fields) for item in parsed_data]
            self.env.cr.executemany(sql_query, sql_params)
            logging.info("Finish insert %d new records in the table %s." % (n_records, self._name))
        except psycopg2.DatabaseError as db_error:
            logging.exception("Error when creating index in the table %s.: %s" % (self._name, db_error),
                              exc_info=True)
            raise db_error
        except Exception as e:
            logging.exception("Another error occur when creating index in the table %s: %s" % (self._name, e),
                              exc_info=True)
            raise e

    ###############################
    # API FUNCTIONS
    ###############################
    @classmethod
    def check_format_rrwf_json_request(cls, json_data):
        """
        Check format of the body of HTTP request in API
        Reordering Rules with Forecast
        :param dict json_data: dict object
        :return bool: True if valid, otherwise raise Error
        """
        try:
            required_fields_for_data = [('product_id', int, None),
                                        ('company_id', int, None)]

            is_valid_format = request_utils.check_json_fields(
                json_data,
                infos_required_field=[('server_pass', str, None),
                                      ('data', list, None)],
                infos_non_required_field=[])

            # check the format of ``data`` fields
            list_data = json_data.get('data', [])
            if is_valid_format:
                required_fields_for_data += [('min_forecast', float, None),
                                             ('max_forecast', float, None),
                                             ('safety_stock', float, None),
                                             ('create_time', str, ExtraFieldType.DATETIME_FIELD_TYPE),
                                             ('pub_time', str, ExtraFieldType.DATETIME_FIELD_TYPE)]

                non_required_fields_for_data = []
                is_valid_format = request_utils.check_format_data_array(
                    list_data,
                    required_fields_for_data=required_fields_for_data,
                    infos_non_required_field=non_required_fields_for_data
                )

        except KeyError as key_error:
            raise key_error
        except TypeError as type_error:
            raise type_error
        except ValueError as value_error:
            raise value_error
        return is_valid_format

    def transform_rrwf_request(self, json_data, extra_fields=None):
        """
        Function transform json request to data import
        :param dict json_data:
        :param list extra_fields:
        :return list[dict]:
        """
        data = json_data.get('data', [])
        transformed_data = copy.deepcopy(data)
        for datum in transformed_data:
            append_log_access_fields_to_data(self, datum, ['write_date', 'write_uid'])
            safety_stock = datum.pop('safety_stock')
            min_forecast = datum.pop('min_forecast')
            max_forecast = datum.pop('max_forecast')
            datum.update({
                'new_safety_stock_forecast': safety_stock,
                'new_safety_stock': safety_stock,
                'new_min_forecast': min_forecast,
                'new_min_qty': min_forecast,
                'new_max_forecast': max_forecast,
                'new_max_qty': max_forecast,
            })

        return transformed_data

    def send_request_to_compute_rrwf_report(self, body_data=None):
        """
        Send a request to FE server to compute reordering rules with forecast report
        :return dict: a JSON format
        """
        try:
            direct_order_url = ServerAPIv1.get_api_url(ServerAPICode.UPDATE_RRWF_REPORT)
            headers = {
                'Content-type': 'application/json',
            }
            auth_content = self.sudo().env['forecasting.config.settings'].get_auth_content()
            body_data = {
                **auth_content,
                "data": body_data
            }
            uuid = auth_content.get('uuid')
            _logger.info("Call API to FE server to recompute Reordering rules with forecast with UUID: %r" % uuid)
            json_body = json.dumps(body_data)
            _logger.info("Make request to server with UUID: %s", uuid)
            response = requests.post(direct_order_url, data=json_body,
                                     headers=headers, timeout=60)
            result = response.json()
        except Exception as e:
            _logger.exception("An exception in send_request_to_compute_rrwf_report.", exc_info=True)
            result = create_response_message(success=False, code=HTTP_400_BAD_REQUEST,
                                             res_msg="Server is busy now. Please try it later.",
                                             detail=e)
            raise
        return result

    def trigger_next_actions(self, created_date, **kwargs):
        self.update_latest_records_in_monitor_model(created_date=created_date)

    def update_latest_records_in_monitor_model(self, created_date):
        """ update records in the tracker, which have the created date as defined in the parameter,
         to the monitor model (reordering.rules.with.forecast model)

        :param datetime created_date:
        :return:
        """
        # Change the latest records in the Monitor model
        monitor_obj = self.env[self._monitor_model].sudo()
        n_rows = monitor_obj.search_count([('create_date', '=', created_date)])
        if self._active_queue_job and n_rows >= self._threshold:
            monitor_obj.delay().update_latest_records(created_date)
        else:
            monitor_obj.update_latest_records(created_date)

    def create_or_update_records(self, vals, forecast_level, **kwargs):
        converted_table_name = get_table_name(self._name)
        forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)
        try:
            # Run SQL code to update new data into the table
            # get insert fields from the data
            inserted_fields = list(vals[0].keys())

            # get conflict fields from forecast level
            conflict_fields = forecast_level_obj.get_conflict_fields_for_rrwf_tracker()
            updated_fields = list(set(inserted_fields) - set(conflict_fields))

            sql_query = """
                INSERT INTO %s (%s)
                VALUES (%s)
                ON CONFLICT (%s)
                DO UPDATE SET
            """ % (converted_table_name,
                   ','.join(inserted_fields),
                   ','.join(["%s"] * len(inserted_fields)),
                   ','.join(conflict_fields))

            sql_query += ", ".join(["%s = EXCLUDED.%s" % (field, field) for field in updated_fields])
            sql_query += ";"

            sql_params = [get_key_value_in_dict(item, inserted_fields) for item in vals]
            self.env.cr.executemany(sql_query, sql_params)
            _logger.info("Insert/update %s rows into the model.", len(vals))

        except IntegrityError:
            logging.exception("Duplicate key in the table %s: %s", converted_table_name, vals, exc_info=True)
            raise
        except Exception:
            _logger.exception("Error in the function create_or_update_records.", exc_info=True)
            raise

    ###############################
    # SCHEDULE FUNCTIONS
    ###############################

    def run_scheduler_truncate_rrwf_tracker(self):
        """
        Run the scheduler to delete out-of-date rows in the table
        Reorder Rules with Forecast Tracker
        :return:
        """
        logging.info("Run the scheduler to delete out-of-date rows in the table "
                     "Reordering Rules with Forecast Tracker")

        sql_query = """
            DELETE FROM reordering_rules_with_forecast_tracker
            WHERE create_date <= (NOW() - INTERVAL '7 DAY');
        """
        self.env.cr.execute(sql_query)

    def run_scheduler_update_rrwf(self):
        """ Schedule Send the data and Request SI Engine compute the Reordering rules with the forecast

        :return:
        """
        try:
            _logger.info("Run scheduler to update Reordering Rules with Forecast.")
            # get the latest data to compute reordering rule with forecast
            newest_data = self._get_newest_rrwf_data()
            _logger.info("New reordering rule with forecast data in the cronjob: %s", json.dumps(newest_data)[:300])
            if newest_data:
                self._create_new_records(new_records=newest_data)
                response = self.send_request_to_compute_rrwf_report(body_data=newest_data)
                if response.get('code') == 200:
                    logging.info("Send a request to FE server to compute Reordering Rules with Forecast is success.")
                else:
                    logging.error("Something is wrong when sending a request to update "
                                  "Reordering Rules with Forecast: %r" %
                                  response.get('res_msg'))
            else:
                _logger.info("Skip the cron job to update Reordering Rules with Forecast because of no new data!")
        except Exception:
            _logger.exception("Exception in the cron job run_scheduler_update_rrwf",
                              exc_info=True)

    ###############################
    # INIT FUNCTIONS
    ###############################
    @api.model
    def create_rrwf_tracker_indices(self):
        """
        Create indices in the table
        :return:
        """
        try:
            sql_query = """
                CREATE UNIQUE INDEX IF NOT EXISTS unique_pcw_id_rrwf_tracker
                ON reordering_rules_with_forecast_tracker (product_id, company_id, warehouse_id, create_time);                                  
            """
            t1 = time()
            self.env.cr.execute(sql_query)
            t2 = time()
            _logger.info("Finish create indices in the table %s in %f (s)." % (self._name, t2 - t1))
        except psycopg2.DatabaseError as db_error:
            _logger.exception("Error when creating index in the table %s.: %s" % (self._name, db_error),
                              exc_info=True)
            raise db_error
        except Exception as e:
            _logger.exception("Another error occur when creating index in the table %s: %s" % (self._name, e),
                              exc_info=True)
            raise e
