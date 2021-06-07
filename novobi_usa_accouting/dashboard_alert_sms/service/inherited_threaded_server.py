# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

import threading
import logging

from odoo.service.server import CommonServer

from .slack import slack_bot

_logger = logging.getLogger(__name__)


# class ThreadedServer(CommonServer):
#     def mess_bot_listen(self):
#         slack_bot.Bot()
#
#     def cron_spawn(self):
#         """ Start the above runner function in a daemon thread.
#
#         The thread is a typical daemon thread: it will never quit and must be
#         terminated when the main process exits - with no consequence (the processing
#         threads it spawns are not marked daemon).
#
#         """
#         super(ThreadedServer, self).cron_spawn()
#
#         def target():
#             self.mess_bot_listen()
#
#         t = threading.Thread(target=target, name="message_apps_listener")
#         t.setDaemon(True)
#         t.type = 'cron'
#         t.start()
#         _logger.debug("message applications listener started!")
