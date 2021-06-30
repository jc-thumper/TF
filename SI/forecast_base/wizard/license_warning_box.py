# -*- coding: utf-8 -*-
import ast

from odoo import models, fields, api, _


class WarningBox(models.TransientModel):
    _name = "forecasting.license.warning.box"
    _description = "License Warning Box"

    # store message to show in a popup confirmation window
    message = fields.Text(default=lambda self: self.env.context.get('message'))

    def accept_confirmation(self):
        """
        @Override
        write the action for button "OK"
        """
        default_act = {'type': 'ir.actions.act_window_close'}
        return default_act
