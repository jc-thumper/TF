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


class ProductForecastConfig(models.Model):
    _inherit = 'product.forecast.config'

    ###############################
    # JOB FUNCTIONS
    ###############################
    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60,
                        6: 10 * 60,
                        9: 30 * 60},
         default_channel='root.forecasting')
    def generate_forecast_config_from_indirect_demand(self, updated_ids, default_period_type=PeriodType.WEEKLY_TYPE):
        """
            Create/Update the Product Forecast Configuration for all items have just update indirect demand

        :param list[int] updated_ids:
        :param str default_period_type:
        :return:
        :rtype:
        """

        # Step 1: check updated_ids whether is empty or not
        # Step 2: if the updated_ids is not empty, we find all forecast result daily from updated_ids
        # Step 3: generate the list of tuple key from forecast results daily
        # Step 3: get the dictionary of product forecast config from the tuple keys
        # Step 4: get
        # Step 5: create the new product forecast config and do nothing if it Violated Constraint
