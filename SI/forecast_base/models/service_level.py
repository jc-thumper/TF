# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ServiceLevel(models.Model):
    _name = "service.level"
    _inherit = 'abstract.product.classification'
    _description = "Service Level"

    _label_json = 'service_level'
    _column_clsf_id = 'service_level_id'
    _column_pub_time = 'sl_pub_time'

    ###############################
    # CONSTANTS
    ###############################
    CATEGORY_A = 'group_a'
    CATEGORY_B = 'group_b'
    CATEGORY_C = 'group_c'
    CATEGORY_NONE = None

    CLSF_NAME = [
        (CATEGORY_A, 'Group A'),
        (CATEGORY_B, 'Group B'),
        (CATEGORY_C, 'Group C')
    ]

    ###############################
    # FIELDS
    ###############################
    name = fields.Selection(CLSF_NAME,
                            string='Service Level')

    ###############################
    # PUBLIC METHODS
    ###############################
    def get_service_levels_ids(self):
        """ Get all records in table

        :return: a dictionary of service level name code and corresponding
        service level id.
        :rtype: dict
        {
            <service_level: string>: <record_id: int>,
            <service_level: string>: <record_id: int>,
            ...
        }
        """
        result = {}
        for record in self.search([]):
            result[record.name] = record.id

        return result

    def name_get(self):
        """ name_get() -> [(id, name), ...]

        Returns a textual representation for the records in ``self``.
        By default this is the value of the ``display_name`` field.

        :return: list of pairs ``(id, text_repr)`` for each records
        :rtype: list(tuple)
        """
        result = []
        name = dict(self.CLSF_NAME)
        for record in self:
            result.append((record.id, name.get(record.name)))

        return result
