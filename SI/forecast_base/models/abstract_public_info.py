# -*- coding: utf-8 -*-

import logging
import numpy as np

from psycopg2._psycopg import AsIs
from psycopg2 import IntegrityError

from odoo import models, fields, api
from odoo.addons.si_core.utils import request_utils
from odoo.addons.si_core.utils.string_utils import get_table_name
from odoo.addons.si_core.utils.database_utils import get_query_params

_logger = logging.getLogger(__name__)


class AbstractPublicInfo(models.AbstractModel):
    _name = "abstract.public.info"
    _inherit = 'abstract.product.info'
    _description = "Abstract Public Info"

    ###############################
    # FIELDS
    ###############################
    pub_time = fields.Datetime(required=True, index=True)

    ###############################
    # HELPER FUNCTIONS
    ###############################
    @classmethod
    def get_required_fields(cls, forecast_level=None):
        parent_required_fields = super(AbstractPublicInfo, cls).get_required_fields(forecast_level)

        required_fields_for_data = [
            ('pub_time', str, request_utils.ExtraFieldType.DATETIME_FIELD_TYPE)
        ]

        return required_fields_for_data + parent_required_fields

    @classmethod
    def get_insert_fields(cls, forecast_level=None):
        parent_insert_fields = super(AbstractPublicInfo, cls).get_insert_fields(forecast_level=forecast_level)

        insert_fields = [
            'pub_time'
        ]
        return parent_insert_fields + insert_fields

    ###############################
    # ABSTRACT FUNCTIONS
    ###############################
    def get_latest_pub_time(self, company_id=None):
        """
        get the latest public time in over the table
        :return:
        :rtype: datetime
        """
        query = """
            SELECT MAX(pub_time) FROM %s %s
        """
        comp_cond = company_id and self.env.cr.mogrify("WHERE company_id = %s",
                                                       [company_id]).decode('utf-8') or ''
        self.env.cr.execute(query, (AsIs(self._table), AsIs(comp_cond),))
        fetch_data = self.env.cr.fetchone()

        latest_time = fetch_data and fetch_data[0] or None
        return latest_time

    def get_latest_records(self, company_id=None):
        """
        get latest records in over the table base on the nearest public time
        get from get_latest_pub_time function
        :return:
        :rtype: list(object)
        """
        latest_pub_time = self.get_latest_pub_time(company_id)
        records = self.search([('pub_time', '=', latest_pub_time)])
        return records

    def get_records_by_create_date(self, create_date):
        """
        get latest records in over the table base on the nearest public time
        get from get_latest_pub_time function
        :return:
        :rtype: list(object)
        """
        records = self.search([('create_date', '=', create_date)])
        return records

    def update_product_info(self, data, extra_fields=None):
        """
        Update data into the table
        :param extra_fields:
        :param data: a list of dict to update the database
        :return: Number of record have updated
        :rtype: tuple(int, str)
        """
        no_records = 0
        create_date = None
        try:
            parsed_data = self._transform_product_info_request(data, extra_fields)
            if parsed_data:
                create_date = parsed_data[0].get('create_date')
                no_records = len(parsed_data)
                # TODO: change _load_product_info_request using forecast level config
                self._load_product_info_request(table_name=self._name, parsed_data=parsed_data)

        except Exception as e:
            _logger.exception("An exception occur in update_product_info", exc_info=True)
            raise e

        return no_records, create_date

    def _transform_product_info_request(self, json_data, extra_fields=None):
        """
        Abstract function transform json request to data import
        :param json_data:
        :param extra_fields:
        :type extra_fields: dict
        :return:
        :rtype: list(dict)
        """
        inserted_fields = []
        query_params = []
        self._append_log_create_datum(inserted_fields, query_params)
        transformed_data = json_data.get('data', [])

        extra_data = dict(zip(inserted_fields, query_params))
        for data in transformed_data:
            data.update(extra_data)
            if extra_fields:
                data.update(extra_fields)

        return transformed_data

    def _load_product_info_request(self, table_name, parsed_data,
                                   insert_fields=None, query_data=None):
        """

        :param table_name:
        :param parsed_data:
        :param insert_fields:
        :param query_data:
        :return:
        """
        if insert_fields is None:
            insert_fields = []
        converted_table_name = get_table_name(table_name)

        # get all company_id in JSON data
        company_ids = np.unique([item.get('company_id') for item in parsed_data]).tolist()

        # get forecast level of all company
        forecast_level_dict = self.env['res.company'].sudo().get_forecast_level_by_company_id(company_ids=company_ids)

        # divide task for each company
        for company_id, forecast_level in forecast_level_dict.items():
            inserted_fields = self.get_insert_fields(forecast_level=forecast_level)

            if insert_fields:
                inserted_fields += insert_fields
            inserted_fields = list(dict.fromkeys(inserted_fields))

            if query_data is None:
                query_data = get_query_params(inserted_fields, parsed_data)

            try:
                # create SQL query
                sql_query_template = """
                    INSERT INTO %s (%s)
                """ % (
                    converted_table_name,
                    ','.join(inserted_fields)
                )
                sql_query_template += " VALUES (%s) ON CONFLICT DO NOTHING;" % (','.join(["%s"] * len(inserted_fields)))
                self.env.cr.executemany(sql_query_template, query_data)
            except IntegrityError as inst:
                logging.exception("Duplicate key in the table %s: %s" % (converted_table_name, str(query_data)),
                                  exc_info=True)
                raise inst
            except Exception as e:
                logging.exception("Error in creating new records in the table %s" % converted_table_name, exc_info=True)
                raise e
