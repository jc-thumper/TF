# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

from . import command


class Event:
	def __init__(self, bot):
		self.bot = bot
		self.command = command.Command()

	def wait_for_event(self):
		events = self.bot.slack_client.rtm_read()
		print(events)
		if events and len(events) > 0:
			for event in events:
				self.parse_event(event)

	def parse_event(self, event):
		if event and 'text' in event and self.bot.bot_name in event['text']:
			self.handle_event(event['user'], event['text'].split(self.bot.bot_name)[1].strip().lower(), event['channel'])

	def handle_event(self, user, command, channel):
		if command and channel:
			print("Received command: " + command + " in channel: " + channel + " from user: " + user)
			response = self.command.handle_command(user, command)
			self.bot.slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)
