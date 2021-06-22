# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

import logging

from slack import WebClient

from odoo import _

_logger = logging.getLogger(__name__)


class SlackConnector:
    # Here will be the instance stored.
    __instance = None

    @staticmethod
    def getInstance(slack_bot_token=None, slack_bot_name=None, reload=False):
        """ Static access method. """
        connector = SlackConnector.__instance
        if slack_bot_name and slack_bot_token:
            if SlackConnector.__instance is None or reload:
                SlackConnector(slack_bot_token, slack_bot_name)
                connector = SlackConnector.__instance
        return connector

    def __init__(self, token, name):
        """ Virtually private constructor. """
        if SlackConnector.__instance is None:
            self.slack_client = WebClient(token)
            self.bot_name = name
            print("test")
            self.bot_id = self.get_bot_id()

            print(self.bot_id)
            _logger.info(_('Id of slack bot is: %s') % self.bot_id)

            if self.bot_id is None:
                _logger.error(_('Error, could not find ') + self.bot_name)
            else:
                SlackConnector.__instance = self

    def get_bot_id(self):
        api_call = self.slack_client.api_call("users.list")
        if api_call.get('ok'):
            print('ok')
            # retrieve all users so we can find our bot
            users = api_call.get('members')
            for user in users:
                print(user.get('name'))
                if 'name' in user and user.get('name') == self.bot_name:
                    return "<@" + user.get('id') + ">"

            return None
