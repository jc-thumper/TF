# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class LicenseConfirmBox(models.TransientModel):
    _name = "forecasting.license.confirm.box"
    _description = "License Confirm Box"

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
