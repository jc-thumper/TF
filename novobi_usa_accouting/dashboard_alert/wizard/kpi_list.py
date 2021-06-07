# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class KPIList(models.TransientModel):
    _name = 'kpi.list'

    # store message to show in a popup confirmation window
    kpi_ids = fields.Many2many('alert.info')

    def create_kpi(self):
        """
        write the action for button "YES"
        :return:
        """
        print('create_kpi')
        action = self.env.ref('dashboard_alert.alert_info_popup_form_action').read()[0]
        action['context'] = {
        }
        return action
        # alert_info_popup_form_action
        # return self.env.context.get('action_confirm')
