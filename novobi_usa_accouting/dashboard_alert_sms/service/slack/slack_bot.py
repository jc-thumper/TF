# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

import time
import logging

from slackclient import SlackClient

from . import event

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

SECONDS_INTERVAL_REFRESH_MESS = 2
SLACK_BOT_TOKEN = 'xoxb-507347031699-551902504915-cRWIUpnuYaQCP82PUYdY7qqK'
SLACK_BOT_NAME = 'alertnovobi'


class Bot(object):
	def __init__(self):
		self.slack_client = SlackClient(SLACK_BOT_TOKEN)
		self.bot_name = SLACK_BOT_NAME
		self.bot_id = self.get_bot_id()
		_logger.info(_("Id of slack bot is: %s") % self.bot_id)

		if self.bot_id is None:
			_logger.error('Error, could not find ' + self.bot_name)

		self.event = event.Event(self)
		self.listen()

	def get_bot_id(self):
		api_call = self.slack_client.api_call("users.list")
		if api_call.get('ok'):
			# retrieve all users so we can find our bot
			users = api_call.get('members')
			for user in users:
				if 'name' in user and user.get('name') == self.bot_name:
					return "<@" + user.get('id') + ">"

			return None

	def listen(self):
		if self.slack_client.rtm_connect(with_team_state=False):
			_logger.info(_("Successfully connected, listening for commands"))
			while True:
				self.event.wait_for_event()
				time.sleep(SECONDS_INTERVAL_REFRESH_MESS)
		else:
			_logger.error(_("Error, Connection Failed"))
