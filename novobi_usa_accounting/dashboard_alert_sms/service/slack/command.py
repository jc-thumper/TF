# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

class Command(object):
	def __init__(self):
		self.commands = {
			"jump" : self.jump,
			"help" : self.help
		}

	def handle_command(self, user, command):
		response = "<@" + user + ">: "

		if command in self.commands:
			response += self.commands[command]()
		else:
			response += "Sorry I don't understand the command: " + command + ". " + self.help()

		return response

	def jump(self):
		return "Kris Kross will make you jump jump"

	def help(self):
		response = "Currently I support the following commands:\r\n"

		for command in self.commands:
			response += command + "\r\n"

		return response
