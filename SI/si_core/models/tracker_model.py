# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
from odoo.addons.si_core.utils.string_utils import get_table_name
from odoo.addons.si_core.utils.request_utils import get_key_value_in_dict
from psycopg2 import IntegrityError

_logger = logging.getLogger(__name__)


class TrackerModel:
    _name = ""
    _monitor_model = ""
    _threshold = 1000
    _active_queue_job = False
    _abstract = True
    # don't create table
    _auto = False

    ########################################################
    # FIELDS
    ########################################################

    create_time = fields.Datetime(help='Store the created time of the request sent from the Odoo client')
    pub_time = fields.Datetime(help='Store the created time of the request sent from the FE server')

    ########################################################
    # MODEL FUNCTIONS
    ########################################################

    def __init__(self):
        self.env = None

    def get_conflict_fields(self, required_fields=None, **kwargs):
        """
        Abstract method
        """
        result = ['create_time']
        if required_fields:
            result += required_fields
        return result

    def manual_update(self, vals, **kwargs):
        """
        Update the table with the new data using SQL code
        :param vals: new value to update into the table
        :type vals: list[dict]
        :return:
        :rtype: None
        """
        converted_table_name = get_table_name(self._name)
        try:
            # Run SQL code to update new data into the table
            # get insert fields from the data
            inserted_fields = list(vals[0].keys())
            conflict_fields = self.get_conflict_fields()
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
            _logger.info("Insert/update %s rows into the tracker model.", len(vals))

        except IntegrityError:
            logging.exception("Duplicate key in the table %s: %s", converted_table_name, vals, exc_info=True)
            raise
        except Exception:
            _logger.exception("Error in the function manual_update.", exc_info=True)
            raise

    def update(self, vals):
        """
        Update the table with the new data using ORM
        :param vals:
        :return:
        """
        super(TrackerModel, self).update(vals)
        # Change the latest records in the Monitor model
        monitor_obj = self.env[self._monitor_model]
        if self._active_queue_job and len(vals) >= self._threshold:
            monitor_obj.sudo().delay().update_latest_records()
        else:
            monitor_obj.update_latest_records()
