# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class DemandClassification(models.Model):
    _name = "demand.classification"
    _inherit = 'abstract.product.classification'
    _description = "Demand Classification"

    _label_json = 'demand_type'
    _column_clsf_id = 'demand_clsf_id'
    _column_pub_time = 'dc_pub_time'

    ###############################
    # CONSTANTS
    ###############################
    CLSF_NAME = [
        ('seasonal', 'Seasonal'),
        ('smooth', 'Smooth'),
        ('intermittent', 'Intermittent'),
        ('lumpy', 'Lumpy'),
        ('erratic', 'Erratic'),
        ('not_enough_data', 'Not Enough Data'),
    ]

    ###############################
    # FIELDS
    ###############################
    name = fields.Selection(selection_add=CLSF_NAME,
                            string='Demand Classification Type')

    ###############################
    # PUBLIC METHODS
    ###############################
    def get_clsf_ids(self):
        """ Get all records in table

        :return: a dictionary of demand classification code and corresponding
        forecast group id.
        :rtype: dict
        {
            <demand_type: string>: <record_id: int>,
            <demand_type: string>: <record_id: int>,
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
