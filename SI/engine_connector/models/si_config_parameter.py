# -*- coding: utf-8 -*-

import uuid
import logging

from odoo import api, fields, models
from odoo.tools import config, ormcache

_logger = logging.getLogger(__name__)

"""
A dictionary holding some configuration parameters to be initialized 
when the database is created.
"""
_default_parameters = {
    "database.secret": lambda: str(uuid.uuid4()),
    "database.uuid": lambda: str(uuid.uuid1()),
    "database.create_date": fields.Datetime.now,
    "web.base.url": lambda: "http://localhost:%s" % config.get('http_port'),
}


class ForecastingConfigParameter(models.Model):
    """
    Store Forecast settings in Configuration Menu with structure
    key-value pairs.
    """
    _name = "forecasting_config_parameter"
    _rec_name = 'key'
    _description = "Forecasting Configuration Parameter"

    key = fields.Char(required=True, index=True)
    value = fields.Text(required=True)

    _sql_constraints = [
        ('key_uniq', 'unique (key)', 'Key must be unique.')
    ]

    def init(self, force=False):
        """
        Initializes the parameters listed in _default_parameters.
        It overrides existing parameters if force is ``True``.
        """
        for key, func in _default_parameters.items():
            # force=True skips search and always performs the 'if' body (because ids=False)
            params = self.sudo().search([('key', '=', key)])
            if force or not params:
                params.set_param(key, func())

    @api.model
    def get_param(self, key, default=False):
        """Retrieve the value for a given key.

        :param string key: The key of the parameter value to retrieve.
        :param string default: default value if parameter is missing.
        :return: The value of the parameter, or ``default`` if it does not exist.
        :rtype: string
        """
        value = self._get_param(key)
        return value or default

    @api.model
    def _get_param(self, key):
        params = self.search_read([('key', '=', key)], fields=['value'], limit=1)
        return params[0]['value'] if params else None

    @api.model
    def set_param(self, key, value):
        """Sets the value of a parameter.

        :param string key: The key of the parameter value to set.
        :param string value: The value to set.
        :return: the previous value of the parameter or False if it did
                 not exist.
        :rtype: string
        """
        param = self.search([('key', '=', key)])
        if param:
            old = param.value
            if value is not False and value is not None:
                param.write({'value': value})
            else:
                param.unlink()
            return old
        else:
            if value is not False and value is not None:
                self.create({'key': key, 'value': value})
            return False

    @api.model
    def create(self, vals):
        self.clear_caches()
        return super(ForecastingConfigParameter, self).create(vals)

    def write(self, vals):
        self.clear_caches()
        return super(ForecastingConfigParameter, self).write(vals)

    def unlink(self):
        self.clear_caches()
        return super(ForecastingConfigParameter, self).unlink()

    ########################################################
    # PRIVATE FUNCTIONS
    ########################################################
    def _get_hashed_password(self):
        return self.get_param('forecasting.si_server_pass', "")
