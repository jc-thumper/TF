# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _

SLACK_BOT_TOKEN = 'slack_bot_token'
SLACK_BOT_TOKEN_KEY = 'dashboard_alert_slack_bot.slack_bot_token'
SLACK_BOT_NAME = 'slack_bot_name'
SLACK_BOT_NAME_KEY = 'dashboard_alert_slack_bot.slack_bot_name'

PARAMS = [
    (SLACK_BOT_TOKEN, SLACK_BOT_TOKEN_KEY),
    (SLACK_BOT_NAME, SLACK_BOT_NAME_KEY),
]


class InheritedResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    slack_bot_token = fields.Char(string="Token", readonly=False, default='')
    slack_bot_name = fields.Char(string="Bot Name", readonly=False, default='')

    @api.model
    def get_values(self):
        res = super(InheritedResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        for field_name, key_name in PARAMS:
            res[field_name] = get_param(key_name, default='')
        return res

    @api.model
    def set_values(self):
        for field_name, key_name in PARAMS:
            field_value = getattr(self, field_name, '')
            value = ('' if not field_value else field_value).strip()
            self.env['ir.config_parameter'].set_param(key_name, value)
        super(InheritedResConfigSettings, self).set_values()
