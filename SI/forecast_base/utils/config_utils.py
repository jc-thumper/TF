# -*- coding: utf-8 -*-

from odoo import _

########################################################
# CONSTANTS VALUE
########################################################
MAX_RETRIES_ON_REGISTER_FAILURE = 5
INSTANTLY_UPDATE_DEFAULT = True
NO_SAFETY_EXPIRE_DATE = 3
DEFAULT_THRESHOLD_TO_TRIGGER_QUEUE_JOB = 10


class ForecastLevelLogicConfig:
    """

    """
    WAREHOUSE_LEVEL = 'warehouse'
    WAREHOUSE_LEVEL_DESCRIPTION = "The system will run the forecast process to determine " \
                                  "the future needs of each product in each warehouse.\n"\
                                  "All of Smart Inventory operations using future forecast demand " \
                                  "will be run at the warehouse level also.\n"\
                                  "You can see the future demand of each product per warehouse " \
                                  "from its product variant form."

    FORECAST_LEVEL_LOGIC = [
        (WAREHOUSE_LEVEL, _('Warehouse'))
    ]

    FORECAST_LEVEL_LOGIC_DESCRIPTION = {
        WAREHOUSE_LEVEL: WAREHOUSE_LEVEL_DESCRIPTION
    }

    @classmethod
    def get_description(cls, forecast_level_logic):
        return cls.FORECAST_LEVEL_DESCRIPTION.get(forecast_level_logic, "")