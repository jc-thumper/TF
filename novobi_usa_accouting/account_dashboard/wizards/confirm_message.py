# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ExtendConfirmMessage(models.TransientModel):
    _name = 'account_dashboard.extend_confirm_message'

    # store message to show in a popup confirmation window
    message = fields.Text(default=lambda self: self.env.context.get('content_message'))

    def accept_confirmation(self):
        """
        write the action for button "YES"
        :return:
        """
        return self.env.context.get('action_confirm')
