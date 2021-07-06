# -*- coding: utf-8 -*-

import logging

from datetime import datetime, timedelta

from odoo.addons import decimal_precision as dp
from odoo.addons.queue_job.job import job

from odoo.addons.queue_job.exception import RetryableJobError

from psycopg2.extensions import AsIs

from odoo.tools import float_compare
from odoo.addons.si_core.utils import database_utils, datetime_utils
from odoo.addons.si_core.utils.string_utils import PeriodType
from ..utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB, ALLOW_TRIGGER_QUEUE_JOB

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ForecastResultAdjustLine(models.Model):
    _name = "forecast.result.adjust.line"
    _inherit = 'abstract.product.info'
    _description = "Forecasting Adjustment Line"
    _order = 'start_date'

    ###############################
    # FIELDS
    ###############################
    forecast_result_adjust_id = fields.Many2one('forecast.result.adjust', required=False, index=True)

    adjust_value = fields.Float(store=True, string='Demand Forecast Adjusted',
                                digits=dp.get_precision('Product Unit of Measure'),
                                help='The total forecast demand after adjusted')
    adjust_percentage = fields.Float(string='Adjust Demand Forecast',
                                     default=0, store=False,
                                     compute='_compute_adjust_percentage',
                                     inverse='_inverse_adjust_percentage',
                                     digits=dp.get_precision('Adjust Percentage'),
                                     help='The Adjust percentage for the total Forecast Demand')
    reason_for_adjustment = fields.Text('Reason for Adjustment',
                                        default='')

    # Forecast Result Information
    forecast_line_id = fields.Many2one('forecast.result', ondelete='cascade')
    forecast_result = fields.Float(string='Demand Forecast', store=True, readonly=True, required=False,
                                   digits=dp.get_precision('Product Unit of Measure'),
                                   help='The sale forecast result of this product')
    fore_pub_time = fields.Datetime(string='Forecast Result Public Time', store=True, readonly=True, required=False)

    # Validation Result Information
    validation_id = fields.Many2one('validation.result', ondelete='cascade')
    validation_result = fields.Float(string='Validation Result', store=True, readonly=True, required=False,
                                     digits=dp.get_precision('Product Unit of Measure'))

    # Summarize Value Information
    summ_data_line_id = fields.Many2one('summarize.data.line')
    picks = fields.Integer(string='Total Orders', related='summ_data_line_id.no_picks')
    picks_with_discount = fields.Integer(string='Order w/Disc',
                                         related='summ_data_line_id.picks_with_discount')

    demand = fields.Float(string='Actual Demand (for All Orders)', related='summ_data_line_id.summarize_value', )
    demand_with_discount = fields.Float(string='Actual Demand (for Disc Orders)',
                                        related='summ_data_line_id.demand_with_discount')

    avg_discount_perc = fields.Float(string='Avg Disc (%)',
                                     related='summ_data_line_id.avg_discount_perc')

    product_id = fields.Many2one('product.product', store=True)
    warehouse_id = fields.Many2one('stock.warehouse', store=True)
    company_id = fields.Many2one('res.company', store=True)

    # General Information
    period_type = fields.Selection(PeriodType.LIST_PERIODS,
                                   readonly=True, store=True)

    start_date = fields.Date()
    end_date = fields.Date()

    # Computed Information
    muted = fields.Boolean(compute='_compute_muted', help='Allow User know this data is the historical data or not')
    has_changed_adjust = fields.Boolean(compute='_compute_has_changed_adjust')

    # Promotion
    has_promotion = fields.Boolean(string='With promo?', default=False,
                                   store=False,
                                   compute='_compute_has_promotion',
                                   help='Check if the current product has any promotion in this period')

    # Demand gap
    demand_gap = fields.Float(string='Adjust Demand Trend', default=0.0, store=True,
                              digits=dp.get_precision('Product Unit of Measure'),
                              help='The gap of demand in case we need to adjust the historical data')

    demand_adjust_value = fields.Float(string='Demand Trend Adjusted', store=False,
                                       compute='_compute_demand_adjust_value',
                                       digits=dp.get_precision('Product Unit of Measure'),
                                       help='Actual demand base on sale historical data')

    has_changed_demand = fields.Boolean(compute='_compute_has_changed_demand',
                                        help='Check if the user changes value of Demand Adjustment '
                                             'for this record or not')

    _sql_constraints = [
        ('forecast_line_id_uniq', 'unique(forecast_line_id)',
         "A forecast result can only be assigned to one adjustment record!"),
        ('summ_data_line_id_uniq', 'unique(summ_data_line_id)',
         "A summarize data can only be assigned to one adjustment record!"),
    ]

    ###############################
    # ONCHANGE FUNCTIONS
    ###############################
    @api.onchange('adjust_percentage')
    def _onchange_adjust_percentage(self):
        for line in self:
            line.adjust_value = max(line.forecast_result + line.adjust_percentage, 0)

    ###############################
    # COMPUTED FUNCTIONS
    ###############################
    @api.depends('adjust_percentage')
    def _compute_has_changed_adjust(self):
        precision = self.env['decimal.precision'].precision_get('Adjust Percentage')

        # for line in self:
        #     if line.forecast_line_id:
        #         self._cr.execute("""
        #                 SELECT adjust_value - forecast_result AS adjust_percent
        #                 FROM forecast_result_adjust_line
        #                 WHERE forecast_line_id = %s
        #         """, (line.forecast_line_id.id,))
        #
        #         origin_percentage = self._cr.fetchone()[0]
        #         line.has_changed_adjust = float_compare(line.adjust_percentage, origin_percentage,
        #                                                 precision_digits=precision)
        #     else:
        #         line.has_changed_adjust = False
        forecast_result_ids = self.mapped(lambda item: item.forecast_line_id.id)
        # Remove None or 0 value
        forecast_result_ids = [item for item in forecast_result_ids if item]

        self._cr.execute("""
            SELECT forecast_line_id AS id, adjust_value - forecast_result AS adjust_percent
            FROM forecast_result_adjust_line
            WHERE forecast_line_id in %s
        """, (tuple(forecast_result_ids),))
        data = self._cr.dictfetchall()

        old_value = {}
        for line in data:
            old_value.setdefault(int(line.get('id')), float(line.get('adjust_percent')))

        for item in self:
            item.has_changed_adjust = float_compare(item.adjust_percentage, old_value.get(item.forecast_line_id.id),
                                                    precision_digits=precision) \
                if item.forecast_line_id \
                else False

    @api.depends('forecast_line_id.end_date')
    def _compute_muted(self):
        """
            Mute past forecast result
        :return:
        """
        datetime_now = datetime.now()
        date_now = datetime_now.date()

        end_date_previous_period_dict = {}
        for period_type, period_text in PeriodType.LIST_PERIODS:
            end_date_previous_period_dict.setdefault(
                period_type,
                datetime_utils.get_start_end_date_value(
                    datetime_now + datetime_utils.get_delta_time(period_type, -1),
                    period_type
                )[1].date()
            )

        for line in self:
            end_date_previous_period = end_date_previous_period_dict.get(line.period_type, date_now)
            line.muted = line.end_date <= end_date_previous_period

    @api.depends('forecast_line_id',
                 'forecast_line_id.start_date',
                 'forecast_line_id.end_date',
                 'forecast_line_id.period_type')
    def _compute_picks_and_demand(self):
        """
        Compute all sale orders of product with delivery date in between start date and end date
        :param: None
        :return: None
        """
        for item in self:
            self._cr.execute("""SELECT product_id 
                FROM forecast_result_adjust_line 
                WHERE id = %s""", (item.id,))
            product_id = self._cr.fetchone()[0]
            sale_order_lines = self.env['sale.order.line'].search(
                [('product_id', '=', product_id),
                 ('order_id.confirmation_date', '<', item.forecast_line_id.end_date),
                 ('order_id.confirmation_date', '>', item.forecast_line_id.start_date)])

            sale_order_ids = sale_order_lines.mapped('order_id')
            item.picks = len(sale_order_ids)
            for line in sale_order_lines:
                item.demand = item.demand + line.product_uom_qty

    @api.depends('adjust_value', 'forecast_result')
    def _compute_adjust_percentage(self):
        """
        Compute adjust percentage base on the original forecast result and the adjustment value from the user
        :return:
        """
        for line in self:
            line.adjust_percentage = line.adjust_value - line.forecast_result

    def _compute_has_promotion(self):
        today = datetime.now().date()
        for line in self:
            # If the forecast end date still in promotion period and the demand with discount > 0,
            # this product has promotion
            line.has_promotion = line.end_date < today and line.demand_with_discount > 0

    @api.depends('demand', 'demand_gap')
    def _compute_demand_adjust_value(self):
        """
            Compute demand in case we have the lift value (the demand gap value) entered by the user.
            We can call this value is the baseline sale
        """
        for line in self:
            line.demand_adjust_value = max(line.demand + line.demand_gap, 0)

    @api.depends('demand_gap')
    def _compute_has_changed_demand(self):
        precision = self.env['decimal.precision'].precision_get('Adjust Percentage')

        for line in self:
            is_change = False
            if line.summ_data_line_id:
                is_change = float_compare(line.demand, line.demand_adjust_value, precision_digits=precision)

            line.has_changed_demand = is_change

    ###############################
    # INVERSE FUNCTIONS
    ###############################
    def _inverse_adjust_percentage(self):
        """
        Update the value of Forecast Adjustment
        :return:
        """
        for line in self:
            line.adjust_value = line.forecast_result + line.adjust_percentage

    ###############################
    # GENERAL FUNCTIONS
    ###############################
    @api.model_create_multi
    def create(self, vals_list):
        _logger.info('before create forecast result adjust line')
        ForecastResultAdjustLine._format_fral(vals_list)
        lines = super(ForecastResultAdjustLine, self).create(vals_list)
        _logger.info('create done with %s rows' % len(vals_list))
        if lines:
            line_ids = lines.ids
            number_of_record = len(line_ids)

            from odoo.tools import config
            threshold_trigger_queue_job = int(config.get("threshold_to_trigger_queue_job",
                                                         DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
            allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                 ALLOW_TRIGGER_QUEUE_JOB)

            if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                self.env['forecast.result.adjust'].sudo().with_delay(max_retries=12) \
                    .update_forecast_result_base_on_lines(line_ids, update_time=True)
            else:
                self.env['forecast.result.adjust'].sudo()\
                    .update_forecast_result_base_on_lines(line_ids, update_time=True)

        return lines

    def create_mul_rows(self, vals_list, constrain_cols=None, conflict_work=None, **kwargs):
        """

        :param list[dict] vals_list: this list of the row data that we use to create/update to table
        forecast_result_adjust_line
        :param list[str] constrain_cols:
        :param str conflict_work:
        :return:
        """
        _logger.info('Create forecast result adjust line')
        ForecastResultAdjustLine._format_fral(vals_list)
        lines = super().create_mul_rows(vals_list, constrain_cols,
                                        get_lines=True, conflict_work=conflict_work)
        if lines:
            line_ids = lines.ids
            number_of_record = len(line_ids)
            forecast_result_adjust_env = self.env['forecast.result.adjust'].sudo()

            from odoo.tools import config
            threshold_trigger_queue_job = int(config.get("threshold_to_trigger_queue_job",
                                                         DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
            allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                 ALLOW_TRIGGER_QUEUE_JOB)

            if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                forecast_result_adjust_env.sudo().with_delay(max_retries=12) \
                    .update_forecast_result_base_on_lines(line_ids, update_time=True)
            else:
                forecast_result_adjust_env.sudo()\
                    .update_forecast_result_base_on_lines(line_ids, update_time=True)

        return lines

    def write(self, values):
        if 'product_id' not in values and 'company_id' not in values \
                and 'warehouse_id' not in values and 'period_type' not in values \
                and 'start_date' not in values and 'end_date' not in values:
            ForecastResultAdjustLine._format_fral(values)
            res = super(ForecastResultAdjustLine, self).write(values)
            if self.check_condition_to_update_forecast_result_adjust(values=values):
                line_ids = self.ids
                self.rounding_forecast_value(line_ids)

                number_of_record = len(line_ids)

                from odoo.tools import config
                threshold_trigger_queue_job = int(config.get("threshold_to_trigger_queue_job",
                                                             DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
                allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                     ALLOW_TRIGGER_QUEUE_JOB)

                if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                    self.env['forecast.result.daily'].sudo() \
                        .with_delay(max_retries=12, eta=10) \
                        .update_forecast_result_daily(line_ids, call_from_engine=True)
                else:
                    self.env['forecast.result.daily'].sudo() \
                        .update_forecast_result_daily(line_ids, call_from_engine=True)

            return res
        else:
            return

    ###############################
    # HELPER FUNCTIONS
    ###############################
    @classmethod
    def get_insert_new_fral_conditions(cls, source_table):
        query_conditions = [
            source_table + '.product_id IS NOT DISTINCT FROM fral.product_id',
            source_table + '.warehouse_id IS NOT DISTINCT FROM fral.warehouse_id',
            source_table + '.company_id IS NOT DISTINCT FROM fral.company_id',
            source_table + '.start_date = fral.start_date'
        ]
        return query_conditions

    @classmethod
    def get_insert_new_fral_with_fore_result(cls):
        return [
            ('adjust_value', '(CASE WHEN fr.forecast_result < 0 THEN 0 ELSE ' +
             'fr.forecast_result END)'),
            ('forecast_line_id', 'fr.id'),
            ('forecast_result', '(CASE WHEN fr.forecast_result < 0 THEN 0 ELSE ' +
             'fr.forecast_result END)'),
            ('product_id', 'fr.product_id'),
            ('warehouse_id', 'coalesce(fr.warehouse_id) as warehouse_id'),
            ('company_id', 'fr.company_id'),
            ('start_date', 'fr.start_date'),
            ('end_date', 'fr.end_date'),
            ('period_type', 'fr.period_type')]

    @classmethod
    def get_insert_new_fral_with_val_result(cls):
        return [
            ('validation_id', 'val.id'),
            ('validation_result', '(CASE WHEN val.validation_result < 0 THEN 0 ELSE val.validation_result END)'),
            ('product_id', 'val.product_id'),
            ('warehouse_id', 'coalesce(val.warehouse_id) as warehouse_id'),
            ('company_id', 'val.company_id'),
            ('start_date', 'val.start_date'),
            ('end_date', 'val.end_date'),
            ('period_type', 'val.period_type')]

    @api.model
    def insert_new_forecast_adjust_lines(self, query_param, company_id):
        """
        Create new forecast result adjust lines for forecast results of new periods
        :param company_id:
        :param query_param: params for insert query
        :type query_param: dict
        :return: None
        """
        constrain_cols_str = ', '.join(self._list_constrain_columns(company_id))
        query = """
        INSERT INTO forecast_result_adjust_line(create_uid, create_date, write_uid, write_date, 
                                                %(extend_insert_fields)s)
        SELECT  %(create_uid)s, %(create_date)s, %(write_uid)s, %(write_date)s, 
                %(extend_get_value_fields)s
        FROM (
            SELECT * 
            FROM forecast_result 
            WHERE create_date = %(for_res_create_date)s) as fr
        LEFT OUTER JOIN (
            SELECT * 
            FROM forecast_result_adjust_line 
            WHERE start_date >= %(now)s 
                OR (end_date >= %(now)s 
                    AND start_date <= %(now)s)) as fral
        ON (
            %(join_conditions)s
        )
        WHERE fr.id IS NOT NULL AND fral.id IS NULL
        ON CONFLICT (%(constrain_cols_str)s) 
        DO UPDATE SET 
            write_date  = EXCLUDED.write_date, 
            forecast_result = EXCLUDED.forecast_result,
            adjust_value = EXCLUDED.forecast_result,
            forecast_line_id = EXCLUDED.forecast_line_id;
        """

        extend_insert_fields = self.get_insert_new_fral_with_fore_result()

        field_format = ' , '.join(
            ['%s'] * len(extend_insert_fields))

        insert_fields_query = self.env.cr.mogrify(field_format,
                                                  [AsIs(field[0]) for field in extend_insert_fields]).decode('utf-8')

        get_value_fields_query = self.env.cr.mogrify(field_format,
                                                     [AsIs(field[1]) for field in extend_insert_fields]).decode('utf-8')

        insert_conditions = self.get_insert_new_fral_conditions(source_table='fr')

        insert_conditions_format = ' AND '.join(
            ['%s'] * len(insert_conditions))

        insert_conditions_query = self.env.cr.mogrify(insert_conditions_format,
                                                      [AsIs(condition) for condition in insert_conditions]).decode(
            'utf-8')

        query_param['extend_insert_fields'] = AsIs(insert_fields_query)
        query_param['extend_get_value_fields'] = AsIs(get_value_fields_query)
        query_param['join_conditions'] = AsIs(insert_conditions_query)
        query_param['constrain_cols_str'] = AsIs(constrain_cols_str)

        self.env.cr.execute(query, query_param)
        self.env.cr.commit()
        self.env.cache.invalidate()

    @api.model
    def insert_new_validation_data(self, query_param, company_id):
        """
        Create new forecast result adjust lines for validation results of new periods
        :param company_id:
        :param query_param: params for insert query
        :type query_param: dict
        :return: None
        """
        constrain_cols_str = ', '.join(self._list_constrain_columns(company_id))
        query = """
            INSERT INTO forecast_result_adjust_line(create_uid, create_date, write_uid, write_date, 
                                                    %(extend_insert_fields)s)
            SELECT  %(create_uid)s, %(create_date)s, %(write_uid)s, %(write_date)s, 
                    %(extend_get_value_fields)s
            FROM (
                SELECT * 
                FROM validation_result 
                WHERE create_date = %(val_res_create_date)s) as val
            LEFT OUTER JOIN (
                SELECT * 
                FROM forecast_result_adjust_line 
                WHERE start_date >= %(now)s 
                    OR (end_date >= %(now)s 
                        AND start_date <= %(now)s)) as fral
            ON (
                %(join_conditions)s
            )
            WHERE val.id IS NOT NULL AND fral.id IS NULL
            ON CONFLICT (%(constrain_cols_str)s) 
            DO UPDATE SET 
                write_date  = EXCLUDED.write_date, 
                validation_result = EXCLUDED.validation_result,
                validation_id = EXCLUDED.validation_id;
            """

        extend_insert_fields = self.get_insert_new_fral_with_val_result()

        field_format = ', '.join(
            ['%s'] * len(extend_insert_fields))

        insert_fields_query = self.env.cr.mogrify(field_format,
                                                  [AsIs(field[0]) for field in extend_insert_fields]).decode('utf-8')

        get_value_fields_query = self.env.cr.mogrify(field_format,
                                                     [AsIs(field[1]) for field in extend_insert_fields]).decode('utf-8')

        insert_conditions = self.get_insert_new_fral_conditions(source_table='val')

        insert_conditions_format = ' AND '.join(
            ['%s'] * len(insert_conditions))

        insert_conditions_query = self.env.cr.mogrify(insert_conditions_format,
                                                      [AsIs(condition) for condition in insert_conditions]).decode(
            'utf-8')

        query_param['extend_insert_fields'] = AsIs(insert_fields_query)
        query_param['extend_get_value_fields'] = AsIs(get_value_fields_query)
        query_param['join_conditions'] = AsIs(insert_conditions_query)
        query_param['constrain_cols_str'] = AsIs(constrain_cols_str)

        self.env.cr.execute(query, query_param)
        self.env.cr.commit()
        self.env.cache.invalidate()

    @classmethod
    def get_update_new_forecast_adjust_lines_conditions(cls, source_table):
        query_conditions = [source_table + '.product_id IS NOT DISTINCT FROM fral.product_id',
                            source_table + '.warehouse_id IS NOT DISTINCT FROM fral.warehouse_id',
                            source_table + '.company_id IS NOT DISTINCT FROM fral.company_id',
                            source_table + '.start_date = fral.start_date',
                            source_table + '.end_date = fral.end_date']
        return query_conditions

    @api.model
    def update_forecast_adjust_line(self, query_param):
        """
        Update old forecast result adjust lines with new forecast results
        :param query_param: params for update query
        :return: None
        """
        # Step 1: find the record that the user has changed the forecast value before

        select_query = """
        SELECT 
            fr.id as new_forecast_line_id, 
            fral.forecast_line_id as old_forecast_line_id, 
            fral.id as fral_id, 
            CASE WHEN fral.adjust_value IS NULL THEN fr.forecast_result
             ELSE fral.adjust_value END as pre_adjust_value, 
            fr.forecast_result as new_fore_value, 
            %(now)s as now
        FROM (
            SELECT * 
            FROM forecast_result 
            WHERE create_date = %(for_res_create_date)s) as fr
        INNER JOIN (
            SELECT * 
            FROM forecast_result_adjust_line 
            WHERE start_date >= %(now)s 
                OR (start_date <= %(now)s) 
                    AND end_date >= %(now)s)as fral
        ON (
                %(join_conditions)s
            )
        """

        insert_conditions = self.get_update_new_forecast_adjust_lines_conditions(source_table='fr')

        insert_conditions_format = ' AND '.join(
            ['%s'] * len(insert_conditions))

        insert_conditions_query = self.env.cr.mogrify(insert_conditions_format,
                                                      [AsIs(condition) for condition in insert_conditions]).decode(
            'utf-8')

        query_param['join_conditions'] = AsIs(insert_conditions_query)

        self.env.cr.execute(select_query, query_param)
        update_params = self.env.cr.dictfetchall()

        # Step 2: reserve the forecast adjustment value changed from the user

        update_query = """
           UPDATE forecast_result_adjust_line
           SET forecast_line_id = %(new_forecast_line_id)s,
                adjust_value = %(pre_adjust_value)s,
                forecast_result = %(new_fore_value)s,
                write_date = %(now)s
           WHERE id = %(fral_id)s
           """

        self.env.cr.executemany(update_query, update_params)
        self.env.cr.commit()
        self.env.cache.invalidate()

    @api.model
    def update_validation_adjust_line(self, query_param):
        """
        Update old forecast result adjust lines with new validation results
        :param query_param: params for update query
        :return: None
        """
        # Step 1: find the record that the user has changed the forecast value before

        select_query = """
            SELECT 
                val.id as validation_id, 
                fral.id as fral_id, 
                val.validation_result as validation_value, 
                %(now)s as now
            FROM (
                SELECT * 
                FROM validation_result 
                WHERE create_date = %(val_res_create_date)s) as val
            INNER JOIN (
                SELECT * 
                FROM forecast_result_adjust_line 
                WHERE start_date >= %(now)s 
                    OR (start_date <= %(now)s) 
                        AND end_date >= %(now)s)as fral
            ON (
                    %(join_conditions)s
                )
            """

        insert_conditions = self.get_update_new_forecast_adjust_lines_conditions(source_table='val')

        insert_conditions_format = ' AND '.join(['%s'] * len(insert_conditions))

        insert_conditions_query = self.env.cr.mogrify(insert_conditions_format,
                                                      [AsIs(condition) for condition in insert_conditions]).decode(
            'utf-8')

        query_param['join_conditions'] = AsIs(insert_conditions_query)

        self.env.cr.execute(select_query, query_param)
        update_params = self.env.cr.dictfetchall()

        # Step 2: reserve the forecast adjustment value changed from the user

        update_query = """
               UPDATE forecast_result_adjust_line
               SET validation_id = %(validation_id)s,
                    validation_result = %(validation_value)s,
                    write_date = %(now)s
               WHERE id = %(fral_id)s
               """

        self.env.cr.executemany(update_query, update_params)
        self.env.cr.commit()
        self.env.cache.invalidate()

    @api.model
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_forecast_adjust_line_table(self, created_date, **kwargs):
        """ Create/Update forecast_result_adjust_line from data in forecast result table.
        All the new records will have a same create_date and write_date.
        Then, the forecast result daily will be updated

        :param str created_date: the created date of the rows in forecast_result table
        that we use to update update to the forecast_result_adjust_line table
        :param kwargs:
        :return datetime: the create_date/write_date of the created/updated records
        """
        try:
            cur_time = database_utils.get_db_cur_time(self.env.cr)
            forecast_level = kwargs.get('forecast_level')
            forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(forecast_level=forecast_level)

            updated_ids = forecast_level_obj \
                .update_records_for_forecast_result_adjust_line(
                    obj=self, model=self.env['forecast.result.adjust.line'],
                    created_date=created_date,
                    **{
                        'current_time': cur_time,
                        'create_uid': self.env.ref('base.partner_root').id,
                        'create_date': cur_time,
                        'write_uid': self.env.ref('base.partner_root').id,
                        'write_date': cur_time
                    }
                )

            _logger.info("%s records have been updated in Forecast Result Adjust Line table: %s",
                         len(updated_ids), updated_ids)
            if updated_ids:
                self.rounding_forecast_value(updated_ids)
                # Step 3 update the daily forecasting result

                number_of_record = len(updated_ids)

                from odoo.tools import config
                threshold_trigger_queue_job = int(config.get("threshold_to_trigger_queue_job",
                                                         DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
                allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                     ALLOW_TRIGGER_QUEUE_JOB)

                if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                    self.env['forecast.result.daily'].sudo() \
                        .with_delay(max_retries=12, eta=10) \
                        .update_forecast_result_daily(updated_ids, call_from_engine=True)
                else:
                    self.env['forecast.result.daily'].sudo() \
                        .update_forecast_result_daily(updated_ids, call_from_engine=True)

            # commit new change to the database
            self.env.cr.commit()

        except Exception:
            _logger.exception('Function update_forecast_adjust_table have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')
        return cur_time

    @api.model
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_validation_val(self, val_res_create_date, company_id):
        """
        Function update forecast result adjust line table from
        new forecast result received from Forecast Engine
        :return:
        """
        try:
            cur_time = database_utils.get_db_cur_time(self.env.cr)
            # Step 1 update old records with any record have existed
            update_query_param = {
                'now': cur_time,
                'val_res_create_date': val_res_create_date
            }
            if val_res_create_date:
                self.update_validation_adjust_line(update_query_param)

            # Step 2 insert new records
            insert_query_param = {
                **update_query_param,
                **{
                    'create_uid': self.env.ref('base.partner_root').id,
                    'create_date': cur_time,
                    'write_uid': self.env.ref('base.partner_root').id,
                    'write_date': cur_time
                }
            }
            self.insert_new_validation_data(insert_query_param, company_id)

            lines = self.search([('write_date', '=', cur_time)])
            _logger.info("Processing %s records in Forecast Result Adjust Line: %s", len(lines.ids), lines.ids)
            if lines:
                line_ids = lines.ids
                self.rounding_forecast_value(line_ids)
                # Step 3 update the daily forecasting result
                number_of_record = len(line_ids)

                from odoo.tools import config
                threshold_trigger_queue_job = int(config.get("threshold_to_trigger_queue_job",
                                                             DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
                allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                     ALLOW_TRIGGER_QUEUE_JOB)

                if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                    self.env['forecast.result.daily'].sudo() \
                        .with_delay(max_retries=12, eta=10) \
                        .update_forecast_result_daily(lines.ids, call_from_engine=True)
                else:
                    self.env['forecast.result.daily'].sudo() \
                        .update_forecast_result_daily(lines.ids, call_from_engine=True)

        except Exception:
            _logger.exception('Function update_forecast_adjust_table have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')

    def create_history_points(self, product_id, warehouse_id, company_id,
                              period_type, no_points=6):
        """ Create old 6 periods from now

        :param no_points:
        :type no_points: int
        :param product_id:
        :param warehouse_id:
        :param company_id:
        :param product_id:
        :param period_type:
        :return:
        """
        start_cur_period, _ = datetime_utils \
            .get_start_end_date_value(datetime.now(), period_type)
        virtual_lines = self
        delta_time = datetime_utils.get_delta_time(period_type)
        for i in range(no_points):
            end_date = start_cur_period - i * delta_time - timedelta(days=1)
            start_date = start_cur_period - (i + 1) * delta_time
            vir_forecast_line_id = self.env['forecast.result'] \
                .create_virtual_fore_result(product_id, warehouse_id, company_id,
                                            period_type, start_date, end_date)
            line = self.create({
                'product_id': product_id,
                'warehouse_id': warehouse_id,
                'company_id': company_id,
                'start_date': start_date,
                'end_date': end_date,
                'forecast_line_id': vir_forecast_line_id
            })
            virtual_lines += line
        return virtual_lines

    def update_values_by_ids(self, new_values):
        """
        Update value in Forecast Result Adjust Line using record id
        :param new_values: New values to update. Each item has the same format bellow
        - field_name is the column name of the table in database
        - field_value is the new value of this field
        {
            'id': 1,
            <field_name>: <field_value>,
            ...
        }
        :type new_values: List[dict]
        """
        if new_values:
            copied_values = new_values.copy()
            updated_values = {
                item.pop('id'): item for item in copied_values
            }
            record_ids = list(updated_values.keys())
            records = self.search([('id', 'in', record_ids)])
            for record in records:
                vals = updated_values.get(record.id)
                if vals:
                    record.write(vals)

    @staticmethod
    def check_condition_to_update_forecast_result_adjust(values):
        """
        Check if some defined columns in the ``values`` or not to trigger the event
        update the value of `forecast.result.adjust`
        :param values: values got from the UI when the user clicks Save button
        :type values: dict
        :rtype: bool
        """
        result = False
        if 'demand' in values \
                or 'adjust_percentage' in values \
                or 'forecast_result' in values \
                or 'adjust_value' in values:
            result = True
        return result

    def rounding_forecast_value(self, line_ids=None):
        """

        :return:
        """
        if line_ids:
            self._cr.execute("""
                    UPDATE forecast_result_adjust_line line
                    SET forecast_result = round(forecast_result/rounding) * rounding,
                        adjust_value = round(adjust_value/rounding) * rounding
                    FROM product_product prod
                      JOIN product_template tmpl
                        ON prod.product_tmpl_id = tmpl.id
                      JOIN uom_uom uu
                        ON tmpl.uom_id = uu.id
                    WHERE line.id IN %s AND prod.id = line.product_id;""", (tuple(line_ids), ))
            self._cr.commit()

    @api.model
    def get_tuple_key(self):
        """

        :return:
        :rtype: tuple
        """
        return (self.product_id.id or None, self.company_id.id or None,
                self.warehouse_id.id or None)

    @staticmethod
    def _format_fral(vals_list):
        """

        :param vals_list:
        :type vals_list: list[dict]
        :return:
        """
        if isinstance(vals_list, list):
            for vals in vals_list:
                ForecastResultAdjustLine._format_forecast_value(vals)
        elif isinstance(vals_list, dict):
            ForecastResultAdjustLine._format_forecast_value(vals_list)

    @staticmethod
    def _format_forecast_value(vals):
        """

        :param vals:
        :type vals: dict
        :return:
        """
        if vals.get('forecast_result', 0) < 0:
            vals['forecast_result'] = 0
        if vals.get('adjust_value', 0) < 0:
            vals['adjust_value'] = 0

    @api.model
    def _list_constrain_columns(self, cid):
        """ Function return the list of unique constrain column of the table forecast_result_adjust_line.
        This constrain depend on the forecast level of company cid

        :return:
        :rtype: list[str]
        """
        forecast_level = self.env['res.company'].sudo().search([('id', '=', cid)]).forecast_level_id

        key_columns = forecast_level.get_list_of_extend_keys() + ['period_type', 'start_date']
        _logger.info('List of constrain columns use for forecast result adjust line is %s' % key_columns)

        return key_columns

    ###############################
    # INIT FUNCTIONS
    ###############################
    def create_index(self):
        # Adding Index
        self._cr.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE indexname = 'forecast_result_adjust_line_pcw_id_ed_idx'
        """)
        if not self._cr.fetchone():
            self._cr.execute("""
                CREATE INDEX forecast_result_adjust_line_pcw_id_ed_idx 
                ON forecast_result_adjust_line (product_id, company_id, warehouse_id, end_date)
            """)

        self._cr.execute("""
                    SELECT indexname FROM pg_indexes 
                    WHERE indexname = 'forecast_result_adjust_line_create_date_idx'
                """)
        if not self._cr.fetchone():
            self._cr.execute("""
                        CREATE INDEX forecast_result_adjust_line_create_date_idx 
                        ON forecast_result_adjust_line (create_date)
                    """)

        # Adding Constrain
        self._cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = %s', ('forcasting_fral_rule_id',))
        if not self._cr.fetchone():
            self._cr.execute(
                """CREATE UNIQUE INDEX forcasting_fral_rule_id ON forecast_result_adjust_line 
                (product_id, company_id, warehouse_id, period_type, start_date)""")
