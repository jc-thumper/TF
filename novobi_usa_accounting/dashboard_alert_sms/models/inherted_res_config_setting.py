# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _

TWILIO_TOKEN = 'twilio_token'
TWILIO_ACC_SID = 'twilio_acc_sid'
TWILIO_SOURCE_PHONE_NUMBER = 'twilio_source_phone_number'
TWILIO_FORMAT_MESS = 'twilio_format_mess'
TWILIO_TOKEN_KEY = 'dashboard_alert_sms.twilio_token'
TWILIO_ACC_SID_KEY = 'dashboard_alert_sms.twilio_acc_sid'
TWILIO_SOURCE_PHONE_NUMBER_KEY = 'dashboard_alert_sms.twilio_source_phone_number'
TWILIO_FORMAT_MESS_KEY = 'dashboard_alert_sms.twilio_format_mess'
MESS_DEFAULT = "'Alert from Odoo - %s: %s %s at %s' % " \
               "(subject, kpi_id_name," \
               "condition_info, comp_info['name'],)"

PARAMS = [
    (TWILIO_TOKEN, TWILIO_TOKEN_KEY),
    (TWILIO_ACC_SID, TWILIO_ACC_SID_KEY),
    (TWILIO_SOURCE_PHONE_NUMBER, TWILIO_SOURCE_PHONE_NUMBER_KEY),
    (TWILIO_FORMAT_MESS, TWILIO_FORMAT_MESS_KEY),
]

DEFAULT_VALUE_DICT = {
    TWILIO_FORMAT_MESS_KEY: MESS_DEFAULT
}


class InheritedResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    twilio_token = fields.Char(string="Token", readonly=False, default='')
    twilio_acc_sid = fields.Char(string="Account SID", readonly=False, default='')
    twilio_source_phone_number = fields.Char(string='Source Phone Number', readonly=False, default='')
    twilio_format_mess = fields.Char('Format SMS Message',
                                     help='Define the format sms message look like define a string in python code.'
                                          'The following variables can be used:'
                                          ' - user_receive: Name of recipient '
                                          ' - subject: Subject of Alert'
                                          ' - creator_name: Name of alert owner'
                                          ' - kpi_id_name: name of KPI in this alert'
                                          ' - kpi_id: KPI\'s id'
                                          ' - condition_info: condition to compare with KPI value'
                                          ' - server_link: link to the dashboard'
                                          ' - comp_info:'
                                          '     - id: company\'s id'
                                          '     - currency_id: currency object'
                                          '     - name: company\'s name'
                                          '     - phone: company\'s phone'
                                          '     - email: company\'s email'
                                          '     - website: company\'s website'
                                     ,
                                     default=MESS_DEFAULT)

    @api.model
    def get_values(self):
        res = super(InheritedResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        for field_name, key_name in PARAMS:
            res[field_name] = get_param(key_name, default=DEFAULT_VALUE_DICT.get(key_name, ''))
        return res

    @api.model
    def set_values(self):
        for field_name, key_name in PARAMS:
            field_value = getattr(self, field_name, DEFAULT_VALUE_DICT.get(key_name, ''))
            value = ('' if not field_value else field_value).strip()
            self.env['ir.config_parameter'].set_param(key_name, value)
        super(InheritedResConfigSettings, self).set_values()
