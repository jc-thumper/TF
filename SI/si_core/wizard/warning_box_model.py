# -*- coding: utf-8 -*-
import ast

from odoo import models, fields, api, _


class WarningBox(models.TransientModel):
    _name = "si_core.warning.box"
    _description = "SI Core Warning Box"

    # store message to show in a popup confirmation window
    message = fields.Text(default=lambda self: self.env.context.get('message'))

    def accept_confirmation(self):
        """
        @Override
        write the action for button "OK"
        """
        default_act = {'type': 'ir.actions.act_window_close'}
        return default_act

    def get_action(self, title='Warning', message='There some problems.', view_id=None):
        """
            Get the action data to return to client
        :param str title:
        :param str message:
        :param int view_id:
        :return: The action data
        :rtype: dict
        """
        if view_id is None:
            view_id = self.env.ref('si_core.view_si_core_warning_box_form').id

        action = {
            'type': 'ir.actions.act_window',
            'name': _(title),
            'res_model': 'si_core.warning.box',
            'view_mode': 'form',
            'target': 'new',
            'views': [[view_id, 'form']],
            'context': {
                'message': message
            }
        }

        return action
