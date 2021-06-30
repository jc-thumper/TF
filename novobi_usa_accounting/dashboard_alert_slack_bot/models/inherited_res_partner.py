# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import logging

from .inherted_res_config_setting import SLACK_BOT_TOKEN_KEY, SLACK_BOT_NAME_KEY
from odoo import api, models, fields, modules, tools, _
from ..connector.slack_connector import SlackConnector

_logger = logging.getLogger(__name__)


class InheritedResPartner(models.Model):
    _inherit = 'res.partner'

    slack_bot = fields.Char('Slack Real Name')
    slack_id = fields.Char(compute='_compute_slack_id', default='')

    ########################################################
    # COMPUTED FUNCTION
    ########################################################
    @api.depends('slack_bot')
    def _compute_slack_id(self):
        for user in self:
            get_param = self.env['ir.config_parameter'].sudo().get_param
            slack_token = get_param(SLACK_BOT_TOKEN_KEY, default='')
            slack_name = get_param(SLACK_BOT_NAME_KEY, default='')
            slack_connector = SlackConnector.getInstance(slack_token, slack_name)

            if slack_connector:
                api_call = slack_connector.slack_client.api_call('users.list')
                if api_call.get('ok'):
                    # retrieve all users so we can find our bot
                    users = api_call.get('members')
                    for slack_user in users:
                        if 'real_name' in slack_user and slack_user.get('real_name') == user.slack_bot:
                            user.slack_id = slack_user.get('id')
            else:
                _logger.warning("Can not connect to slack client")

    def partner_contact_save(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_context',
        }
