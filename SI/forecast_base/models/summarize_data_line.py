# -*- coding: utf-8 -*-

import logging
import math

from odoo.addons.queue_job.job import job
from odoo.addons.queue_job.exception import RetryableJobError

from ..utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB, ALLOW_TRIGGER_QUEUE_JOB

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class SummarizeDataLine(models.Model):
    _name = "summarize.data.line"
    _inherit = 'abstract.product.info'
    _description = "Summarize Data Line"

    summ_rec_id = fields.Many2one('summarize.rec.result', required=True)

    start_date = fields.Date(related='summ_rec_id.start_date', store=True)
    end_date = fields.Date(related='summ_rec_id.end_date', store=True)
    period_type = fields.Selection(related='summ_rec_id.period_type', readonly=True, store=True)

    summarize_value = fields.Float(related='summ_rec_id.summarize_value', store=True)
    no_picks = fields.Integer(related='summ_rec_id.no_picks', store=True)
    picks_with_discount = fields.Integer(related='summ_rec_id.picks_with_discount', store=True, readonly=True)
    demand_with_discount = fields.Float(related='summ_rec_id.demand_with_discount', store=True, readonly=True)
    avg_discount_perc = fields.Float(related='summ_rec_id.avg_discount_perc', store=True, readonly=True)

    _sql_constraints = [
        ('pcw_sd_pt_uniq',
         'unique (product_id, company_id, warehouse_id, start_date, period_type)',
         'The tuple product, company, warehouse id must be unique within an application!')
    ]

    def init(self):
        self._cr.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE indexname = 'summarize_data_pcw_id_sd_pt_idx'
            """)
        if not self._cr.fetchone():
            self._cr.execute("""
                    CREATE INDEX summarize_data_pcw_id_sd_pt_idx 
                    ON summarize_data_line (product_id, company_id, warehouse_id, start_date, period_type)
                """)

        self._cr.execute("""
                        SELECT indexname FROM pg_indexes 
                        WHERE indexname = 'summarize_data_line_write_date_idx'
                    """)
        if not self._cr.fetchone():
            self._cr.execute("""
                            CREATE INDEX summarize_data_line_write_date_idx 
                            ON summarize_data_line (write_date)
                        """)

    @staticmethod
    def _get_summarize_data_vals_to_update_fral(summarized_record):
        """
        Extract data from `summarized_record` to update to the table Forecast Result Adjust Line
        :param summarized_record: a record object of Summarize Data Line
        :type summarized_record: recordset
        :return:
        :rtype: dict
        """
        result = {
            'product_id': summarized_record.product_id.id or None,
            'company_id': summarized_record.company_id.id or None,
            'warehouse_id': summarized_record.warehouse_id.id or None,

            'start_date': summarized_record.start_date,
            'end_date': summarized_record.end_date,
            'period_type': summarized_record.period_type,

            'summ_data_line_id': summarized_record.id
        }

        return result

    ###############################
    # JOB FUNCTIONS
    ###############################
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_summarize_data(self, created_date=None, company_id=None):
        """

        :param created_date:
        :param int company_id:
        :return:
        """
        try:
            forecast_level = self.env['res.company'].browse(company_id).forecast_level_id
            forecast_level_name = forecast_level.name
            forecast_level_obj = self.env['forecast.level.strategy'].sudo()\
                .create_obj(forecast_level=forecast_level_name)

            line_ids = forecast_level_obj.update_records_for_summarize_data_line(obj=self,
                                                                                 created_date=created_date)

            # Step: update demand to summarize data line
            _logger.info("Processing %s records in Summarize Data Line: %s...", len(line_ids), line_ids[:50])
            pack_size = 100
            no_packs = math.ceil(len(line_ids) / pack_size)

            from odoo.tools import config
            threshold_trigger_queue_job = int(config.get("threshold_to_trigger_queue_job",
                                                         DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB))
            allow_trigger_queue_job = config.get('allow_trigger_queue_job',
                                                 ALLOW_TRIGGER_QUEUE_JOB)
            for pack_num in range(no_packs):
                range_end = min(len(line_ids), pack_size * (pack_num + 1))
                segment_ids = line_ids[pack_num * pack_size:range_end]

                number_of_record = len(segment_ids)

                if allow_trigger_queue_job and number_of_record >= threshold_trigger_queue_job:
                    self.sudo().with_delay(max_retries=12).update_adjust_line_table(segment_ids, company_id)
                else:
                    self.sudo().update_adjust_line_table(segment_ids, company_id)

        except Exception:
            _logger.exception('Function update_summarize_data have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')

    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_adjust_line_table(self, summ_line_ids, company_id):
        """ Function update data in table `forecast_result_adjust_line`
        with any rows have been writen to table `summarize_data_line` at `write_time`

        :param list[int] summ_line_ids: list of id of records in table `summarize_data_line`
        :param int company_id:
        :return: None
        """
        try:
            _logger.info('Update forecast result adjust line table')
            new_summ_lines = self.search([('id', 'in', summ_line_ids)])
            fore_adj_line_env = self.env['forecast.result.adjust.line']

            dict_data = list(new_summ_lines.mapped(lambda line:
                                                   self._get_summarize_data_vals_to_update_fral(line)))
            if dict_data:
                adj_line_constrain_cols = fore_adj_line_env._list_constrain_columns(company_id)
                fore_adj_line_env.create_mul_rows(dict_data,
                                                  constrain_cols=adj_line_constrain_cols,
                                                  conflict_work='UPDATE SET (write_date, summ_data_line_id) = '
                                                                '(EXCLUDED.write_date, EXCLUDED.summ_data_line_id)'
                                                  )
        except Exception:
            _logger.exception('function update_adjust_line_table have some exception', exc_info=True)
            raise RetryableJobError('Must be retried later')
