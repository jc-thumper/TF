# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import logging

from ..connector.slack_connector import SlackConnector
from .inherted_res_config_setting import SLACK_BOT_NAME_KEY, SLACK_BOT_TOKEN_KEY, SLACK_BOT_NAME, SLACK_BOT_TOKEN
from odoo import api, models, fields, modules, tools, _

_logger = logging.getLogger(__name__)

CHANNEL_SLACK = 'slack_bot'

CHANNELS = [(CHANNEL_SLACK, 'Slack')]


class AlertChannel(models.Model):
    _inherit = "alert.channel"
    _description = "Channels are used to alert to user"

    def get_status_slack_bot_channel(self, receiver, context):
        available_to_send = True

        user_slack_id = receiver.slack_id
        get_param = self.env['ir.config_parameter'].sudo().get_param
        slack_token = get_param(SLACK_BOT_TOKEN_KEY, default='')
        slack_name = get_param(SLACK_BOT_NAME_KEY, default='')
        if user_slack_id:
            context.update({
                'user_slack_id': user_slack_id,
                SLACK_BOT_TOKEN: slack_token,
                SLACK_BOT_NAME: slack_name
            })
        else:
            available_to_send = False
        return available_to_send

    def send_alert_via_slack_bot(self, context):
        slack_connector = SlackConnector.getInstance(context.get(SLACK_BOT_TOKEN_KEY), context.get(SLACK_BOT_NAME_KEY))
        user_slack_id = context.get('user_slack_id')

        if user_slack_id and slack_connector:
            subject = context.get('subject')
            comp_info = context.get('comp_info')
            kpi_id_name = context.get('kpi_id_name')
            creator_name = context.get('creator_name')
            condition_info = context.get('condition_info')
            server_link = context.get('server_link')

            list_btn = context.get('list_btn')
            actions_btn = []
            for btn in list_btn:
                actions_btn.append({
                    "type": "button",
                    "name": "btn_%s_alert" % btn.get('code'),
                    "text": btn.get('name'),
                    "url": btn.get('url'),
                    "style": "primary"
                })

            text_mess = '*%s*\n' \
                        '%s of %s was %s.\n' \
                        'View more: %s' \
                        % \
                        (subject, kpi_id_name, comp_info.get('name'),
                         condition_info, server_link,)
            mess = {
                'channel': user_slack_id,
                'text': text_mess,
                'as_user': True,
                "attachments": [
                    {
                        "fallback": "Alert setting",
                        "actions": actions_btn
                    }
                ]
            }

            slack_connector.slack_client.api_call("chat.postMessage", timeout=None, **mess)
            return True
        else:
            _logger.warning(
                "Can sent the slack message with subject is \"%s\" of user %s" %
                (self.subject, self.user_alert_id.name))
            return False

    ########################################################
    # INITIAL DATA
    ########################################################
    @api.model
    def _add_slack_channel(self):
        for code, name in CHANNELS:
            channel = self.search([('channel_code', '=', code)])
            if not channel:
                self.create({
                    'channel_code': code,
                    'name': name
                })
            else:
                channel.write({
                    'name': name
                })
