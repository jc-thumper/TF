# -*- coding: utf-8 -*-

import json
import logging
import math
from datetime import datetime
from time import sleep

from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo.addons.si_core.utils import datetime_utils, database_utils
from psycopg2.extensions import AsIs

from odoo import models, fields, api

from odoo.addons.queue_job.job import job
from odoo.addons.queue_job.exception import RetryableJobError

_logger = logging.getLogger(__name__)


class ForecastResultAdjust(models.Model):
    _inherit = 'forecast.result.adjust'
