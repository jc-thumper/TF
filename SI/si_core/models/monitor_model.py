# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _


class MonitorModel:
    _abstract = True
    # don't create table
    _auto = False
    _tracker_model = ''
    tracker_id = fields.Many2one(_tracker_model)

    ########################################################
    # MODEL FUNCTIONS
    ########################################################

    def get_latest_records(self):
        """
        Implement the logic to return the latest records
        The logic is implemented in the sub class.
        :return: a list of record_id
        :rtype: a list of int
        """
        raise NotImplementedError("Function get_latest_records is not implemented.")

    def update_latest_records(self):
        """
        Update the relation to the latest record in the Tracker Model.
        :return:
        """
        raise NotImplementedError("Function update_latest_records is not implemented.")
