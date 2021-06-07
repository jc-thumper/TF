# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

import logging

from twilio.rest import Client

from odoo import _

_logger = logging.getLogger(__name__)


class TwilioConnector:
    # Here will be the instance stored.
    __instance = None

    @staticmethod
    def getInstance(twilio_token=None, twilio_acc_sid=None, reload=False):
        """ Static access method. """
        connector = TwilioConnector.__instance
        if twilio_token and twilio_acc_sid:
            if TwilioConnector.__instance is None or reload:
                TwilioConnector(twilio_acc_sid, twilio_token)
                connector = TwilioConnector.__instance
        return connector

    def __init__(self, account_sid, auth_token):
        """ Virtually private constructor. """
        if TwilioConnector.__instance is None:
            self.twilio_client = Client(account_sid, auth_token)

            if self.twilio_client is None:
                _logger.error(_('Error, could not access to twilio with provided information'))
            else:
                TwilioConnector.__instance = self
