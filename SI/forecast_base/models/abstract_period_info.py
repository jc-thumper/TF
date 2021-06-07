# -*- coding: utf-8 -*-

from odoo.addons.si_core.utils.string_utils import PeriodType
from odoo import models, fields, api
from odoo.addons.si_core.utils import request_utils


class AbstractPeriodInfo(models.AbstractModel):
    _name = "abstract.period.info"
    _inherit = 'abstract.public.info'
    _description = "Abstract Period Info"

    ###############################
    # FIELDS
    ###############################
    start_date = fields.Date()
    end_date = fields.Date()
    period_type = fields.Selection(PeriodType.LIST_PERIODS)

    ###############################
    # HELPER FUNCTIONS
    ###############################
    @classmethod
    def get_required_fields(cls, forecast_level=None):
        parent_required_fields = super(AbstractPeriodInfo, cls).get_required_fields(forecast_level)

        required_fields_for_data = [
            ('start_date', str, request_utils.ExtraFieldType.DATE_FIELD_TYPE),
            ('end_date', str, request_utils.ExtraFieldType.DATE_FIELD_TYPE),
            ('period_type', str, None)
        ]
        return required_fields_for_data + parent_required_fields

    @classmethod
    def get_insert_fields(cls, forecast_level=None):
        parent_insert_fields = super(AbstractPeriodInfo, cls).get_insert_fields(forecast_level)

        insert_fields = [
            'start_date',
            'end_date',
            'period_type'
        ]

        return parent_insert_fields + insert_fields
