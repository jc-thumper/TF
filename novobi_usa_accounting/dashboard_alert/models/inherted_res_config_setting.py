# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _


class InheritedResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_dashboard_alert_sms = fields.Boolean(string='Notify by SMS')
    module_dashboard_alert_slack_bot = fields.Boolean(string='Notify by Slack')
