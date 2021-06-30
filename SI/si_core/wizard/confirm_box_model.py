# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ConfirmBox(models.TransientModel):
    _name = "si_core.confirm.box"
    _description = "SI Core Confirm Box"

    # store message to show in a popup confirmation window
    message = fields.Text(default=lambda self: self.env.context.get('message'))

    def accept_confirmation(self):
        """
        @Override
        write the action for button "YES"
        """
        ctx = self.env.context
        default_act = {'type': 'ir.actions.act_window_close'}
        accept_func_name = ctx.get('accept_func_name', '')
        if accept_func_name:
            binding_model = ctx.get('binding_model', '')
            func = getattr(self.env[binding_model], accept_func_name, None)
            result = func()
            return result
        else:
            return default_act

    def cancel_confirmation(self):
        """
        @Override
        write the action for button "NO"
        """
        default_act = {'type': 'ir.actions.act_window_close'}
        return default_act

    def get_action(self, title='Confirm', message='Please confirm.', binding_model=None,
                   accept_func_name=None, view_id=None):
        """
            Get the action data to return to client
        :param str title:
        :param str message:
        :param str binding_model:
        :param str accept_func_name:
        :param int view_id:
        :return: The action data
        :rtype: dict
        """
        if view_id is None:
            view_id = self.env.ref('si_core.view_si_core_confirm_box_form').id

        action = {
            'type': 'ir.actions.act_window',
            'name': _(title),
            'res_model': 'si_core.confirm.box',
            'view_mode': 'form',
            'target': 'new',
            'views': [[view_id, 'form']],
            'context': {
                'message': message,
                'binding_model': binding_model,
                'accept_func_name': accept_func_name,
            },
        }

        return action

