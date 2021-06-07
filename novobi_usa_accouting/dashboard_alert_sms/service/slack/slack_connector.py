# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

import logging

from slackclient import SlackClient

from odoo import _

_logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = 'xoxb-507347031699-551902504915-cRWIUpnuYaQCP82PUYdY7qqK'
SLACK_BOT_NAME = 'alertnovobi'


class SlackConnector:
    # Here will be the instance stored.
    __instance = None

    @staticmethod
    def getInstance():
        """ Static access method. """
        if SlackConnector.__instance is None:
            SlackConnector(SLACK_BOT_TOKEN, SLACK_BOT_NAME)
        return SlackConnector.__instance

    def __init__(self, token, name):
        """ Virtually private constructor. """
        if SlackConnector.__instance is None:
            self.slack_client = SlackClient(token)
            self.bot_name = name
            self.bot_id = self.get_bot_id()
            _logger.info(_("Id of slack bot is: %s") % self.bot_id)

            if self.bot_id is None:
                _logger.error('Error, could not find ' + self.bot_name)
            else:
                SlackConnector.__instance = self

    def get_bot_id(self):
        api_call = self.slack_client.api_call("users.list")
        if api_call.get('ok'):
            # retrieve all users so we can find our bot
            users = api_call.get('members')
            for user in users:
                if 'name' in user and user.get('name') == self.bot_name:
                    return "<@" + user.get('id') + ">"

            return None
