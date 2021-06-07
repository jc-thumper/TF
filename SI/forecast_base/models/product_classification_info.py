# -*- coding: utf-8 -*-

import logging
import psycopg2

from odoo.addons.queue_job.job import job

from odoo.addons.queue_job.exception import RetryableJobError
from odoo import models, fields, api, _

from odoo import SUPERUSER_ID
from odoo.addons.si_core.utils.database_utils import query, get_query_params, \
    generate_where_clause, get_db_cur_time
from odoo.addons.si_core.utils.string_utils import get_table_name
from odoo.addons.si_core.utils.datetime_utils import DEFAULT_DATETIME_FORMAT
from ..utils.config_utils import DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB

from time import time

_logger = logging.getLogger(__name__)


class ProductClassificationInfo(models.Model):
    _name = "product.classification.info"
    _inherit = 'abstract.product.info'
    _description = "Product Classification Info"

    ###############################
    # DEFAULT FUNCTIONS
    ###############################
    def _default_demand_clsf_id(self):
        xml_id = "forecasting.demand_classification_not_enough_data"
        return self.env.ref(xml_id, raise_if_not_found=False)

    def _default_service_level_id(self):
        xml_id = "forecasting.service_level_level_c"
        return self.env.ref(xml_id, raise_if_not_found=False)

    def _default_forecast_group_id(self):
        xml_id = "forecasting.forecast_group_not_enough_data"
        return self.env.ref(xml_id, raise_if_not_found=False)

    ###############################
    # FIELDS
    ###############################
    service_level_id = fields.Many2one('service.level', string='Service Level',
                                       ondelete='cascade', store=True,
                                       compute="_compute_service_level_id",
                                       inverse="_inverse_service_level_id",
                                       default=_default_service_level_id)

    service_level_pub_time = fields.Datetime(string='Service Level Pub Time', store=True,
                                             help="Check the result created from the request with the pub_time")

    service_level_result_id = fields.Many2one('service.level.result', compute='_compute_service_level_result_id')

    demand_clsf_id = fields.Many2one('demand.classification', string='Demand Classification',
                                     ondelete='cascade', store=True,
                                     compute="_compute_demand_clsf_id",
                                     inverse="_inverse_demand_clsf_id",
                                     default=_default_demand_clsf_id)

    demand_clsf_pub_time = fields.Datetime(string='Demand Classification Pub Time', store=True,
                                           help="Check the result created from the request with the pub_time")

    forecast_group_id = fields.Many2one('forecast.group', string='Forecast Group',
                                        ondelete='cascade', store=True,
                                        compute="_compute_forecast_group_id",
                                        default=_default_forecast_group_id)

    active = fields.Boolean(compute="_compute_active", search="_search_active")

    client_available = fields.Boolean(compute='_compute_client_available',
                                      search='_search_client_available', default=False)

    ###############################
    # ONCHANGE FUNCTIONS
    ###############################
    @api.onchange('service_level_id')
    def _onchange_service_level_id(self):
        return {
            'warning': {
                'title': _("Warning"),
                'message': _("When the Service Level value is changed. "
                             "It will make a huge effect on the system. \n"
                             "Let discard if it not necessary!")
            }
        }

    @api.onchange('demand_clsf_id')
    def _onchange_demand_clsf_id(self):
        return {
            'warning': {
                'title': _("Warning"),
                'message': _("When the Demand Classification value is changed. "
                             "It will make a huge effect on the system. \n"
                             "Let discard if it not necessary!")
            }
        }

    ###############################
    # COMPUTED FUNCTIONS
    ###############################
    def _compute_service_level_result_id(self):
        slr_env = self.env['service.level.result']
        company = self.env.user.company_id
        company_id = company.id
        forecast_level_id = company.forecast_level_id
        has_warehouse_level = forecast_level_id.get_has_warehouse_level()
        get_product_field = forecast_level_id.get_product_field()
        for pci in self:
            domain = [
                ('pub_time', '=', pci.service_level_pub_time),
                ('has_approved', '=', True),
                ('company_id', '=', company_id),
                (get_product_field, '=', pci.product_id.id)
            ]
            if has_warehouse_level:
                domain += [('warehouse_id ', '=', pci.warehouse_id.id)]
            pci.service_level_result_id = slr_env.search(domain, limit=1)

    def _compute_client_available(self):
        client_available = self.env['forecasting.config.settings'].check_client_available()
        for product in self:
            product.client_available = client_available

    @api.depends('service_level_id', 'demand_clsf_id')
    def _compute_active(self):
        for product in self:
            if product.service_level_id and product.demand_clsf_id:
                product.active = True
            else:
                product.active = False

    # compute only 1 time?
    def _compute_service_level_id(self):
        for clsf in self:
            # get the latest actual_sl_id in the table service.level.result which has ``has_approved`` is True
            record = query(self.env.cr, table_name='service.level.result',
                           selected_fields='actual_sl_id',
                           domain=[('has_approved', '=', True)],
                           order_by='pub_time desc',
                           limit=1)

            # set the value for the field
            clsf.service_level_id = record[0].get('id') if record else None

    def _inverse_service_level_id(self):
        for clsf in self:
            # update the current value of the field ``service_level_id``
            # to ``actual_sl_id`` in the table service.level.result
            current_value = clsf.service_level_id.id
            pid = clsf.product_id.id
            cid = clsf.company_id.id
            wid = clsf.warehouse_id.id
            store_table = 'service.level.result'
            try:
                sql_query = """
                    UPDATE service_level_result SET 
                        actual_sl_id = %s, 
                        write_date = NOW()
                    WHERE 
                        product_id = %s AND company_id = %s AND warehouse_id = %s AND lot_stock_id is NULL AND
                        pub_time = (SELECT MAX(pub_time) FROM service_level_result
                                    WHERE product_id = %s AND company_id = %s AND warehouse_id = %s AND 
                                    lot_stock_id is NULL);
                """
                self.env.cr.execute(sql_query, [current_value, pid, cid, wid, pid, cid, wid])
            except psycopg2.DatabaseError as db_error:
                logging.exception(
                    "Error when set service level id back into the table %s.: %s" % (store_table, db_error),
                    exc_info=True)
                raise db_error
            except Exception as e:
                logging.exception("Another error occur when set service level id back into the table %s: %s" %
                                  (store_table, e),
                                  exc_info=True)
                raise e

    # compute only 1 time?
    def _compute_demand_clsf_id(self):
        for clsf in self:
            # get the latest actual_sl_id in the table service.level.result which has ``has_approved`` is True
            record = query(self.env.cr, table_name='demand.classification.result',
                           selected_fields='actual_dc_id',
                           domain=[('has_approved', '=', True)],
                           order_by='pub_time desc',
                           limit=1)

            # set the value for the field
            clsf.demand_clsf_id = record[0].get('id') if record else None

    # compute only 1 time?
    @api.depends('demand_clsf_id')
    def _compute_forecast_group_id(self):
        for clsf in self:
            # get current value of demand_clsf_id
            demand_clsf_id = clsf.demand_clsf_id.id
            record = query(self.env.cr, table_name='forecast.group',
                           selected_fields='id',
                           domain=[('demand_clsf_id', '=', demand_clsf_id)])
            default_value = self.env.ref('forecast_base.forecast_group_not_enough_data')
            clsf.forecast_group_id = int(record[0].get('id')) if record else default_value

    ###############################
    # SEARCH FUNCTION
    ###############################
    def _search_client_available(self, operator, value):
        if operator not in ('=', '!='):
            raise ValueError('Invalid operator: %s' % (operator,))
        if not isinstance(value, bool):
            raise ValueError('Invalid value type: %s' % (value,))
        client_available = self.env['forecasting.config.settings'].check_client_available()
        if value ^ client_available:
            domain = [('id', '=', '-1')]
        else:
            domain = []
        return domain

    def _search_active(self, operator, value):
        if operator not in ('=', '!=', '<>'):
            raise ValueError('Invalid operator: %s' % (operator,))

        if not value:
            operator = operator == '=' and '!=' or '='

        if self._uid == SUPERUSER_ID:
            return [(1, '=', 1)]

        pro_clsf_info_ids = []
        if value:
            pro_clsf_info_ids = self.with_context(active_test=False).search([
                '|',
                ('service_level_id', '!=', None),
                ('demand_clsf_id', '!=', None)
            ]).ids

        op = operator == '=' and 'in' or 'not in'
        # don't use param named because orm will add other param (test_active, ...)
        return [('id', op, pro_clsf_info_ids)]

    ###############################
    # GENERAL FUNCTION
    ###############################
    def name_get(self):
        """ name_get() -> [(id, name), ...]

        Returns a textual representation for the records in ``self``.
        By default this is the value of the ``display_name`` field.

        :return: list of pairs ``(id, text_repr)`` for each records
        :rtype: list(tuple)
        """
        result = []
        for record in self:
            result.append((record.id, record.product_id.product_tmpl_id.name))

        return result

    ###############################
    # API FUNCTIONS
    ###############################
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def update_product_classification_infos(self, json_data=None, recomputed_fields=None, source_table=None, **kwargs):
        try:
            forecast_level = kwargs.get('forecast_level')
            created_date = kwargs.get('created_date')
            if forecast_level:
                forecast_level_obj = self.env['forecast.level.strategy'].sudo().create_obj(
                    forecast_level=forecast_level)
                func_code = "update_product_clsf_info_from_%s" % source_table
                if hasattr(forecast_level_obj, func_code):
                    func = getattr(forecast_level_obj, func_code)
                    updated_ids = func(
                        obj=self,
                        model=self.env['product.classification.info'],
                        **{
                           'created_date': created_date
                        }
                    )

                    # trigger computed functions to update value of forecast_group
                    # base on the new value of demand_clsf_id/service_level_id
                    just_updated = self.sudo().search([('id', 'in', updated_ids)])
                    just_updated.modified(recomputed_fields)

                    number_of_record = len(updated_ids)

                    from odoo.tools import config
                    threshold_trigger_queue_job = config.get("threshold_to_trigger_queue_job",
                                                             DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB)

                    if number_of_record < threshold_trigger_queue_job:
                        self.env['product.forecast.config'].sudo() \
                            .update_comp_config_data(
                                json_data,
                                kwargs.get('update_active', False)
                            )
                    else:
                        self.env['product.forecast.config'].sudo()\
                            .with_delay(max_retries=12)\
                            .update_comp_config_data(
                                json_data,
                                kwargs.get('update_active', False)
                            )

        except Exception as e:
            _logger.exception('Function update_product_classification_infos have some exception: %s' % e)
            raise RetryableJobError('Must be retried later')

    ###############################
    # HELPER FUNCTIONS
    ###############################
    def get_product_clsf_info(self, product_domain):
        """ return the corresponding product classification info with the dictionary key in
        prod_info. hence, it just return 1 record

        :param product_domain:
        :return:
        """
        product_clsf_info_id = None
        try:
            product_clsf_info_id = self.with_context(active_test=False).sudo() \
                .search(product_domain, limit=1)
        except (Exception,):
            _logger.warning('Having some errors when get product classification info', exc_info=True)
        return product_clsf_info_id

    def find_existed_records(self, selected_fields=[], field_names=[], values=[]):
        sql_query = "SELECT "

        if selected_fields:
            sql_query += ",".join(selected_fields)
        else:
            # by default, search all column in the table
            sql_query += "*"

        sql_query += " FROM " + get_table_name(self._name)

        where_clause, query_params = generate_where_clause(field_names=field_names, values=values)
        sql_query += " WHERE " + where_clause
        sql_query += ";"

        return sql_query, query_params

    def get_classification_info(self, product_id, company_id=None, warehouse_id=None):
        return self.get_product_info(product_id, company_id, warehouse_id)

    def check_status_of_update_product_classification_info(self, data_info):
        """
        Check product classification info is updated in the Odoo database or not
        :param data_info: info to check
        :type data_info: list[dict]
        :return: a list of dict
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
        :rtype: tuple
        """
        result = []
        is_continue = False
        _logger.info('Data info, that is used to check status of classification process :%s' % str(data_info))
        try:
            for item in data_info:
                company_id = item.get('company_id')
                demand_clsf_pub_time = item.get('demand_clsf_pub_time')
                demand_clsf_records = item.get('demand_clsf_records')
                service_level_pub_time = item.get('service_level_pub_time')
                service_level_records = item.get('service_level_records')

                sql_query = """
                    SELECT id, service_level_id, demand_clsf_id, demand_clsf_pub_time, service_level_pub_time
                    FROM product_classification_info
                    WHERE company_id = %s AND (demand_clsf_pub_time = %s OR service_level_pub_time = %s);
                """
                sql_param = (company_id, demand_clsf_pub_time, service_level_pub_time)
                self.env.cr.execute(sql_query, sql_param)

                records = self.env.cr.dictfetchall()
                _logger.info("Records in Product Classification Info to check forecast condition: %s", records[:1])
                no_service_levels = 0
                no_demand_clsf = 0
                record_ids = []
                for rec in records:
                    service_level_id = rec.get('service_level_id')
                    sl_pub_time = rec.get('service_level_pub_time')
                    dl_pub_time = rec.get('demand_clsf_pub_time')
                    sl_pub_time = sl_pub_time.strftime(DEFAULT_DATETIME_FORMAT) if sl_pub_time is not None \
                        else sl_pub_time
                    dl_pub_time = dl_pub_time.strftime(DEFAULT_DATETIME_FORMAT) if dl_pub_time is not None \
                        else dl_pub_time
                    if service_level_id is not None and sl_pub_time == service_level_pub_time:
                        no_service_levels += 1

                    demand_clsf_id = rec.get('demand_clsf_id', None)
                    if demand_clsf_id is not None and dl_pub_time == demand_clsf_pub_time:
                        no_demand_clsf += 1
                        record_ids.append(rec.get('id'))

                status = no_service_levels == service_level_records and no_demand_clsf == demand_clsf_records

                result.append({
                    "company_id": company_id,
                    "status": status,
                    "product_clsf_info_ids": record_ids
                })

            # if all status of company is False, we will stop at this step.
            is_continue = any([item.get('status') for item in result])

        except Exception:
            _logger.exception("An exception raise when check status of classification process.", exc_info=True)
            raise
        return result, is_continue

    ###############################
    # PRIVATE FUNCTIONS
    ###############################
    def _inverse_demand_clsf_id(self):
        for clsf in self:
            # update the current value of the field ``service_level_id``
            # to ``actual_sl_id`` in the table service.level.result
            current_value = clsf.demand_clsf_id.id
            pid = clsf.product_id.id
            cid = clsf.company_id.id
            wid = clsf.warehouse_id.id
            store_table = 'demand.classification.result'
            try:
                sql_query = """
                    UPDATE demand_classification_result SET 
                        actual_dc_id = %s, 
                        write_date = now()
                    WHERE 
                        product_id = %s AND company_id = %s AND warehouse_id = %s AND lot_stock_id is NULL AND
                        pub_time = (SELECT max(pub_time) FROM demand_classification_result
                                    WHERE product_id = %s AND company_id = %s AND warehouse_id = %s AND 
                                    lot_stock_id is NULL);
                """
                self.env.cr.execute(sql_query, [current_value, pid, cid, wid, pid, cid, wid])
            except psycopg2.DatabaseError as db_error:
                logging.exception("Error when set demand clsf id back into the table %s.: %s" % (store_table, db_error),
                                  exc_info=True)
                raise db_error
            except Exception as e:
                logging.exception("Another error occur when set demand clsf id back into the table %s: %s" %
                                  (store_table, e),
                                  exc_info=True)
                raise e

    ###############################
    # INITIAL FUNCTIONS
    ###############################
    @api.model
    def _create_unique_indices(self):
        """
        Create unique indices for columns in table
        :return:
        """
        try:
            sql_query = """
                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_idx
                ON product_classification_info (product_id)
                WHERE company_id is NULL AND warehouse_id is NULL AND lot_stock_id is NULL;
    
                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_idx
                on product_classification_info (product_id, company_id)
                where warehouse_id is NULL AND lot_stock_id is NULL;
    
                CREATE UNIQUE INDEX IF NOT EXISTS unique_product_company_warehouse_idx
                on product_classification_info (product_id, company_id, warehouse_id);
    
                CREATE UNIQUE INDEX IF NOT EXISTS unique_product
                ON product_classification_info (product_id, company_id, warehouse_id, lot_stock_id);
            """
            t1 = time()
            self.env.cr.execute(sql_query)
            t2 = time()
            logging.info("Finish create indices in the table %s in %f (s)." % (self._name, t2 - t1))
        except psycopg2.DatabaseError as db_error:
            logging.exception("Error when creating index in the table %s.: %s" % (self._name, db_error),
                              exc_info=True)
            raise db_error
        except Exception as e:
            logging.exception("Another error occur when creating index in the table %s: %s" % (self._name, e),
                              exc_info=True)
            raise e
