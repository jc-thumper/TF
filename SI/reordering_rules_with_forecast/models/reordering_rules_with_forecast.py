# -*- coding: utf-8 -*-

import logging
import psycopg2

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from psycopg2._psycopg import AsIs
from .inherit_res_config_settings import ResConfigSettings
from time import time

from odoo.addons.queue_job.job import job
from odoo.addons.si_core.utils.string_utils import PeriodType, ServiceLevel, get_table_name
from odoo.addons.si_core.utils import datetime_utils
from odoo.addons.si_core.models.monitor_model import MonitorModel
from odoo.addons import decimal_precision as dp
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ReorderingRulesWithForecast(models.Model, MonitorModel):
    _name = "reordering.rules.with.forecast"
    _inherit = 'reordering.rules.with.forecast.tracker'
    _description = "Reordering rules with Forecasting Result"
    _tracker_model = 'reordering.rules.with.forecast.tracker'
    _abstract = False
    _auto = True

    ###############################
    # DEFAULT FUNCTION
    ###############################
    @api.model
    def default_get(self, fields):
        res = super(ReorderingRulesWithForecast, self).default_get(fields)
        return res

    ###############################
    # MODEL FIELDS
    ###############################
    forecasting_qty = fields.Char('Novobi Forecasts', readonly=False, compute='_compute_forecast_qty',
                                  help="This value have been computed from 'Forecasting System' application",
                                  store=False, default=-1)

    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', default=False)
    product_uom = fields.Many2one(related='orderpoint_id.product_uom')
    category_id = fields.Many2one(related='product_id.product_tmpl_id.categ_id',
                                  readonly=True, required=True,
                                  default=lambda self: self._context.get('category_id', False))

    qty_available = fields.Float(
        'Quantity On Hand',
        compute='_compute_qty_available',
        digits=dp.get_precision('Product Unit of Measure'),
        store=False, default=0)

    total_demand = fields.Float(
        'Demand', digits=dp.get_precision('Product Unit of Measure'),
        compute='_compute_total_demand',
        help="", default=0, store=False)
    total_supply = fields.Float(
        'Supply', digits=dp.get_precision('Product Unit of Measure'),
        compute='_compute_total_supply',
        help="", default=0, store=False)

    safety_stock = fields.Float(
        'Safety Stock', digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, related='orderpoint_id.safety_stock',
        help='An additional quantity of an item held in the inventory to reduce the '
             'risk that the item will be out of stock.', default=0)
    product_min_qty = fields.Float(
        'Minimum Quantity', digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, related='orderpoint_id.product_min_qty',
        help='When the virtual stock goes below the Min Quantity specified for this field, '
             'Odoo generates a procurement to bring the forecasted quantity to the Max Quantity.',
        default=0)
    product_max_qty = fields.Float(
        'Maximum Quantity', digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, related='orderpoint_id.product_max_qty',
        help='When the virtual stock goes below the Min Quantity, Odoo generates '
             'a procurement to bring the forecasted quantity to the Quantity specified as Max Quantity.', default=0)

    name = fields.Char(
        'Reordering Rule', copy=False,
        readonly=True, related='orderpoint_id.name')

    probably_trigger = fields.Boolean('Probably Trigger', store=False, search='_search_probably_trigger')
    demand_value = fields.Float('Demand Value', store=False, search='_search_demand_value')
    eoq = fields.Float('EOQ', required=False, default=0)

    ###############################
    # IGNORE FIELDS
    ###############################
    service_level_name = fields.Char(required=False, store=False)
    service_level = fields.Float(required=False, store=False)
    lead_times = fields.Char(required=False, store=False)
    summarize_data = fields.Char(required=False, store=False)
    demand_data = fields.Char(required=False, store=False)
    min_max_frequency = fields.Char(required=False, store=False)
    holding_cost = fields.Float(required=False, store=False)
    po_flat_cost = fields.Float(required=False, store=False)
    mo_flat_cost = fields.Float(required=False, store=False)
    route_code = fields.Integer(required=False, store=False)
    standard_price = fields.Float(required=False, store=False)
    lead_days = fields.Integer(required=False, store=False)
    rrwf_id = fields.Many2one(required=False, store=False)

    ###############################
    # MODEL FUNCTIONS
    ###############################

    def get_latest_records_dict(self, created_date):
        """
        Get reordering rules data in the tracker table (reordering.rules.with.forecast.tracker)
        to update to the monitor table

        :param datetime created_date:
        :return list[dict]:
        """
        try:
            sql_query = """
                SELECT 
                    *
                FROM reordering_rules_with_forecast_tracker tracker
                WHERE tracker.create_date = %s;
           """
            sql_param = (created_date,)
            self.env.cr.execute(sql_query, sql_param)
            data_dict = self.env.cr.dictfetchall()
        except Exception as e:
            _logger.exception("Error in the function get_latest_records.", exc_info=True)
            raise e
        return data_dict

    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_latest_records(self, created_date):
        """ The job support sync the new min max from the tracker table (reordering.rules.with.forecast.tracker)
        to the monitor (reordering.rule.with.forecast)

        :param created_date:
        :return:
        """
        try:
            latest_records = self.get_latest_records_dict(created_date)
            # create new record if it doesn't exist and update the existing records with
            # the new min/max suggested quantity
            sql_query = """
                INSERT INTO reordering_rules_with_forecast AS monitor (
                    tracker_id, eoq, create_time, pub_time, 
                    new_min_forecast, new_max_forecast, new_safety_stock_forecast, 
                    new_min_qty, new_max_qty, new_safety_stock,
                    product_id, company_id, warehouse_id, location_id, master_product_id, lot_stock_id, 
                    create_uid, create_date, write_uid, write_date)
                SELECT id,
                       eoq,
                       create_time,
                       pub_time,
                       new_min_forecast,
                       new_max_forecast,
                       new_safety_stock_forecast,
                       new_min_qty,
                       new_max_qty,
                       new_safety_stock,
                       product_id, company_id, warehouse_id, location_id, master_product_id,
                       lot_stock_id, create_uid, create_date, write_uid, write_date
                FROM reordering_rules_with_forecast_tracker tracker
                WHERE tracker.create_date = %(create_date)s
                ON CONFLICT (product_id, company_id, warehouse_id)
                DO UPDATE SET
                    tracker_id = excluded.tracker_id,
                    eoq = excluded.eoq,
                    create_time = excluded.create_time,
                    pub_time = excluded.pub_time,
                    new_min_forecast = excluded.new_min_forecast,
                    new_max_forecast = excluded.new_max_forecast,
                    new_safety_stock_forecast = excluded.new_safety_stock_forecast,
                    new_min_qty = excluded.new_min_qty,
                    new_max_qty = excluded.new_max_qty,
                    new_safety_stock = excluded.new_safety_stock,
                    create_uid = excluded.create_uid,
                    create_date = excluded.create_date,
                    write_uid = excluded.write_uid,
                    write_date = excluded.write_date; 
            """

            self.env.cr.execute(sql_query, {
                'create_date': created_date
            })
            updated_ids = [item.get('tracker_id') for item in latest_records]
            self.env.cr.commit()
            self._auto_update_new_changes_to_rr(updated_ids)
        except Exception:
            _logger.exception("Error in the function update_latest_records.", exc_info=True)
            raise

    ###############################
    # ONCHANGE FUNCTIONS
    ###############################
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            product_tmpl = self.product_id.product_tmpl_id
            product_uom = product_tmpl.uom_id
            self.product_uom = product_uom.id
            self.category_id = product_tmpl.categ_id
            return {'domain': {'product_uom': [('category_id', '=', product_uom.category_id.id)]}}
        return {'domain': {'product_uom': []}}

    ###############################
    # COMPUTE FUNCTIONS
    ###############################
    def _compute_total_demand(self):
        _logger.info("_compute_total_demand")
        today = datetime.now()
        product_ids = [record.product_id.id for record in self]

        curr_forecast_level = self.env.user.company_id.forecast_level
        forecast_level_strategy_obj = self.env['forecast.level.strategy'].search(
            [('name', '=', curr_forecast_level)],
            limit=1)
        forecast_level_obj = forecast_level_strategy_obj.get_object()

        total_demand_dict = forecast_level_obj.get_total_demand_inventory(obj=self, model_name=self._name,
                                                                          product_ids=product_ids, current_date=today)
        _logger.info("Total demand in RRwF: %s", total_demand_dict)
        for record in self:
            product_id = record.product_id.id
            record.total_demand = total_demand_dict.get(product_id, 0.0)

    def _compute_total_supply(self):
        _logger.info("_compute_total_supply")
        today = datetime.now()
        product_ids = [record.product_id.id for record in self]

        curr_forecast_level = self.env.user.company_id.forecast_level
        forecast_level_strategy_obj = self.env['forecast.level.strategy'].search(
            [('name', '=', curr_forecast_level)],
            limit=1)
        forecast_level_obj = forecast_level_strategy_obj.get_object()

        total_supply_dict = forecast_level_obj.get_total_supply_inventory(obj=self, model_name=self._name,
                                                                          product_ids=product_ids, current_date=today)
        _logger.info("Total supply in RRwF: %s", total_supply_dict)
        for record in self:
            product_id = record.product_id.id
            record.total_supply = total_supply_dict.get(product_id, 0.0)

    @api.depends()
    def _compute_forecast_qty(self):
        period_type = self.env['ir.config_parameter'].sudo() \
            .get_param('reordering_rules_with_forecast.min_max_update_frequency',
                       default=ResConfigSettings.DEFAULT_FREQUENCY_UPDATE)
        _, end_cur_period = datetime_utils.get_start_end_date_value(datetime.now(), period_type)
        end_date = end_cur_period.date()

        no_digits = self.env['decimal.precision'].search([('name', '=', 'Product Unit of Measure')]).digits
        unit = {
            PeriodType.WEEKLY_TYPE: ' units/week',
            PeriodType.MONTHLY_TYPE: ' units/month',
            PeriodType.QUARTERLY_TYPE: ' units/quarterly',
            PeriodType.YEARLY_TYPE: ' units/year'
        }[period_type]
        for rule in self:
            demand_qty = rule.cal_forecast_qty(end_date, period_type, no_digits)
            rule.forecasting_qty = demand_qty and demand_qty + unit

    @api.depends()
    def _compute_range_of_period_info(self):
        self.update_reordering_rule_cur_period()

    @api.depends('product_id')
    def _compute_qty_available(self):
        curr_forecast_level = self.env.user.company_id.forecast_level
        forecast_level_obj = self.env['forecast.level.strategy'].search([('name', '=', curr_forecast_level)],
                                                                        limit=1).get_object()
        forecast_level_obj.compute_qty_on_hand(obj=self, model_name=self._name)

    ###############################
    # SEARCH EVENT
    ###############################
    @api.model
    def _search_probably_trigger(self, operator, value):
        if operator not in ('=', '!=', '<>'):
            raise ValueError('Invalid operator: %s' % (operator,))

        if not value:
            operator = operator == "=" and '!=' or '='

        if self._uid == SUPERUSER_ID:
            return [(1, '=', 1)]

        reordering_rules = self.env['stock.warehouse.orderpoint'].search([])

        forecast_result_daily_db = self.env['forecast.result.daily']
        date_now = datetime.now()
        start_date, end_date = datetime_utils.get_start_end_date_value(date_now, 'monthly')
        rule_ids = []
        for rr_rule in reordering_rules:
            forecasted_qty = rr_rule.product_id.virtual_available
            forecast_result_this_month = forecast_result_daily_db.sudo().search(
                [('product_id', '=', rr_rule.product_id.id),
                 ('date', '>', start_date),
                 ('date', '<', end_date)])
            forecast_result_this_month = sum(
                [forecast.daily_forecast_result for forecast in forecast_result_this_month])

            if forecasted_qty - forecast_result_this_month < rr_rule.product_min_qty:
                rule_ids.append(rr_rule.id)

        op = operator == "=" and "in" or "not in"
        return [('id', op, rule_ids)]

    @api.model
    def _search_demand_value(self, operator, operand):
        if operand:
            cur = datetime.strftime(datetime.now() + relativedelta(months=-12), DEFAULT_SERVER_DATE_FORMAT)

            query = """
                SELECT product_id
                FROM stock_move
                WHERE date >= %s
                  AND state = 'done'
                  AND location_dest_id in %s
                GROUP BY product_id
                HAVING %s %s SUM(product_qty * (-price_unit));"""

            list_dest_customer = self.env['stock.location'].search([('usage', '=', 'customer')]).ids

            self.env.cr.execute(query, (cur, tuple(list_dest_customer), operand, AsIs(operator),))
            value_return = self.env.cr.dictfetchall()

            return [('product_id', 'in', list(map(lambda item: item['product_id'], value_return)))]
        else:
            if operator == '=':
                return [('product_id', 'in', [])]
            elif operator == '!=':
                return []

    ###############################
    # GENERAL FUNCTION
    ###############################
    def write(self, values):
        if values.get('new_min_qty', None) is not None and values.get('new_max_qty', None) is not None:
            if values.get('new_min_qty') > values.get('new_max_qty'):
                raise UserError(_("You can not set New Minimum Quantity greater than New Maximum Quantity"))
        elif values.get('new_min_qty', None) is not None:
            for rule in self:
                if rule.new_max_qty < values.get('new_min_qty'):
                    raise UserError(_("You can not set New Minimum Quantity greater than New Maximum Quantity"))
        elif values.get('new_max_qty', None) is not None:
            for rule in self:
                if rule.new_min_qty > values.get('new_max_qty'):
                    raise UserError(_("You can not set New Maximum Quantity greater than New Minimum Quantity"))

        return super(ReorderingRulesWithForecast, self).write(values)

    ###############################
    # ACTION FUNCTIONS
    ###############################
    def reset_reordering_rule(self, records):
        for rule in records:
            rule.write({
                'new_min_qty': rule.new_min_forecast,
                'new_max_qty': rule.new_max_forecast,
                'new_safety_stock': rule.new_safety_stock
            })

    def apply_reordering_rules(self, records):
        view_id = self.env.ref('reordering_rules_with_forecast.view_forecasting_confirm_box_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Confirmation'),
            'res_model': 'wizard.rrwf.confirm.box',
            'view_id': view_id,
            'view_mode': 'form',
            'view_type': 'form',
            'context': {
                'message': 'Do you want to apply new min and max quantity to reordering rules?',
                'record_ids': str(records.ids),
            },
            'target': 'new',
        }

    ###############################
    # HELP FUNCTIONS
    ###############################
    def generate_new_reordering_rules(self, auto_generate_new_rr=True, allow_max_is_zero=False):
        """

        :param allow_max_is_zero:
        :param bool auto_generate_new_rr: the flag is used to know allow or not generate
        new reordering rule automatically
        :return None:
        """
        for rule in self:
            if rule.new_min_qty > rule.new_max_qty:
                raise ValueError("New minimum quantity value need to less than new maximum quantity")
            else:

                # update data for reordering rules table
                if rule.orderpoint_id:
                    if allow_max_is_zero or rule.new_max_qty != 0:
                        rule.orderpoint_id.write({
                            'product_max_qty': rule.new_max_qty,
                            'product_min_qty': rule.new_min_qty,
                            'safety_stock': rule.new_safety_stock
                        })
                else:
                    if auto_generate_new_rr or rule.company_id.auto_gen_rule:
                        if allow_max_is_zero or rule.new_max_qty != 0:
                            company_id, warehouse_id = rule.get_comp_wh_info()
                            location_id = warehouse_id.lot_stock_id
                            reordering_rules = self.env['stock.warehouse.orderpoint'] \
                                .search([('product_id', '=', rule.product_id.id),
                                         ('company_id', '=', company_id.id),
                                         ('warehouse_id', '=', warehouse_id.id),
                                         ('location_id', '=', location_id.id)])
                            if reordering_rules:
                                reordering_rules.write({
                                    'product_max_qty': rule.new_max_qty,
                                    'product_min_qty': rule.new_min_qty,
                                    'safety_stock': rule.new_safety_stock
                                })
                                rule.write({'orderpoint_id': reordering_rules.id})
                            else:
                                values = {
                                    'product_id': rule.product_id.id,
                                    'company_id': company_id.id,
                                    'warehouse_id': warehouse_id.id,
                                    'location_id': location_id.id,
                                    'product_max_qty': rule.new_max_qty,
                                    'product_min_qty': rule.new_min_qty,
                                    'safety_stock': rule.new_safety_stock
                                }
                                self.env['stock.warehouse.orderpoint'] \
                                    .with_context(not_create_rrwf=True, rrwf_id=rule.id).create(values)

    @api.model
    def get_comp_wh_info(self):
        """ Function get company and warehouse information of current
        recommendation reordering rules

        :return:
        :rtype: tuple
        """
        if self.warehouse_id:
            warehouse_id = self.warehouse_id
            company_id = warehouse_id.company_id
        else:
            if self.company_id:
                company_id = self.company_id
            else:
                company_id = self.env.user.company_id
            warehouse_id = self.env['stock.warehouse'] \
                .search([('company_id', '=', company_id.id)], limit=1)
        return company_id, warehouse_id

    def get_forecasting_quantity(self, product_id, company_id, warehouse_id,
                                 start_date, end_date, period_type):
        """

        :param product_id:
        :param company_id:
        :param warehouse_id:
        :param start_date:
        :param end_date:
        :param period_type:
        :return: return forecasting quantity if it exist or return None if not
        :rtype: float
        """
        fore_qty = None
        period_infos = PeriodType.PERIOD_SIZE
        forecast = self.env['forecast.result.adjust.line'].sudo().search([
            ('product_id', '=', product_id),
            ('company_id', '=', company_id),
            ('warehouse_id', '=', warehouse_id),
            ('start_date', '=', start_date),
            ('end_date', '=', end_date),
            ('period_type', '=', period_type),
            ('adjust_value', '!=', None)
        ])
        if forecast:
            fore_qty = forecast.adjust_value
        else:
            for period in period_infos.keys():
                if period != period_type:
                    forecast = self.env['forecast.result.adjust.line'].sudo().search([
                        ('product_id', '=', product_id),
                        ('company_id', '=', company_id),
                        ('warehouse_id', '=', warehouse_id),
                        ('period_type', '=', period),
                        ('end_date', '>=', start_date), ('start_date', '<=', end_date),
                        ('adjust_value', '!=', None)
                    ])
                    if forecast:
                        total_days = len(forecast) * period_infos[period]
                        total_demands = sum(forecast.mapped('adjust_value'))
                        fore_qty = total_demands * period_infos[period_type] / total_days
                        break
        return fore_qty

    ###############################
    # PRIVATE FUNCTION
    ###############################
    def _auto_update_new_changes_to_rr(self, rrwf_ids):
        """ The function support user automatically update new change in reordering rules with forecast
         to the odoo reordering rules

        :param list[int] rrwf_ids:
        :return:
        """
        if self.env.user.company_id.auto_apply_rule:
            rrwf_ids = self.search([('tracker_id', 'in', rrwf_ids)])
            rrwf_ids.generate_new_reordering_rules(auto_generate_new_rr=False, allow_max_is_zero=True)

    @api.model
    def cal_forecast_qty(self, end_date, period_type, no_digits=None):
        """ Calculate Forecasting quantity

        :param date end_date: the end date of current period.
        :param str period_type:
        :param Union[int, None] no_digits:
        :return str:
        """
        forecasting_qty = ''
        if not no_digits:
            no_digits = self.env['decimal.precision'].search([('name', '=', 'Product Unit of Measure')]).digits
        product_id = self.product_id.id
        if product_id:
            next_start_date = end_date + timedelta(days=1)
            _, next_end_date = datetime_utils \
                .get_start_end_date_value(next_start_date, period_type)

            forecast_result = self \
                .get_forecasting_quantity(product_id, self.company_id.id, self.warehouse_id.id,
                                          next_start_date, next_end_date, period_type)
            if forecast_result is not None:
                forecasting_qty = ('%' + '0.%sf' % no_digits) % forecast_result
        return forecasting_qty

    ###############################
    # INITIAL FUNCTION
    ###############################
    @api.model
    def init_data_reordering_rules_with_forecast(self):
        """
        Function initial data for this model base on
        data of model 'stock.warehouse.orderpoint' and model 'forecast.result.adjust'
        :return:
        """
        forecast_level = self.env.user.company_id.forecast_level
        _logger.info("Init records for RRwF with forecast level = %s", forecast_level)
        forecast_level_strategy_obj = self.env['forecast.level.strategy']
        forecast_level_obj = forecast_level_strategy_obj.create_obj(forecast_level=forecast_level)
        forecast_level_obj.create_initial_records_for_rrwf(obj=self, model_name=self._name)

    @api.model
    def create_rrwf_indices(self):
        """
        Create indices in the table
        :return:
        """
        try:
            sql_query = """
                CREATE UNIQUE INDEX IF NOT EXISTS unique_pcw_id_rrwf
                ON reordering_rules_with_forecast (product_id, company_id, warehouse_id);                                  
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
