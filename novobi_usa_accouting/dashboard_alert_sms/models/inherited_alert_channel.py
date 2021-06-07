# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import logging

from odoo.tools.safe_eval import safe_eval
from ..models.inherted_res_config_setting import TWILIO_TOKEN_KEY, TWILIO_ACC_SID_KEY, \
    TWILIO_SOURCE_PHONE_NUMBER_KEY, TWILIO_TOKEN, TWILIO_ACC_SID, TWILIO_SOURCE_PHONE_NUMBER, \
    MESS_DEFAULT, TWILIO_FORMAT_MESS_KEY
from ..connector.twilio_connector import TwilioConnector
from odoo import api, models, fields, modules, tools, _

_logger = logging.getLogger(__name__)

CHANNEL_SMS = 'sms'

CHANNELS = [(CHANNEL_SMS, 'SMS')]


class InheritedAlertChannel(models.Model):
    _inherit = "alert.channel"
    _description = "Channels are used to alert to user"

    def get_status_sms_channel(self, receiver, context):
        available_to_send = True

        sms_number = receiver.mobile
        if sms_number:
            get_param = self.env['ir.config_parameter'].sudo().get_param
            twilio_token = get_param(TWILIO_TOKEN_KEY, default='')
            twilio_acc_sid = get_param(TWILIO_ACC_SID_KEY, default='')
            twilio_source_phone_number = get_param(TWILIO_SOURCE_PHONE_NUMBER_KEY, default='')
            context.update({
                'sms_number': sms_number,
                TWILIO_TOKEN: twilio_token,
                TWILIO_ACC_SID: twilio_acc_sid,
                TWILIO_SOURCE_PHONE_NUMBER: twilio_source_phone_number
            })
        else:
            available_to_send = False
        return available_to_send

    def send_alert_via_sms(self, context):
        send_status = False
        try:
            twilio_connector = TwilioConnector.getInstance(context[TWILIO_TOKEN], context[TWILIO_ACC_SID])
            if twilio_connector:
                code = 'text_mess = ' + self.env['ir.config_parameter'].sudo()\
                    .get_param(TWILIO_FORMAT_MESS_KEY, MESS_DEFAULT)
                safe_eval(code, context, mode="exec", nocopy=True)
                text_mess = context.get('text_mess', '')
                twilio_connector.twilio_client.messages \
                    .create(body=text_mess,
                            from_=context[TWILIO_SOURCE_PHONE_NUMBER],
                            to=context['sms_number']
                            )
            _logger.info("Send SMS successful")
            send_status = True
        except:
            _logger.warning("Some problem happen when send alert via sms")
        return send_status

    ########################################################
    # INITIAL DATA
    ########################################################
    @api.model
    def _add_sms_channel(self):
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
