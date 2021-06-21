# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import logging

from odoo.addons.account_dashboard.utils.utils import convert_value_with_unit_type

from ..utils.utils import get_margin_value, format_currency_amount
from odoo import api, models, fields, modules, tools, _

_logger = logging.getLogger(__name__)

CHANNEL_PRIMARY_EMAIL = 'email'

DEFAULT_CHANNELS = [
    (CHANNEL_PRIMARY_EMAIL, 'Email'),
]

CHANNELS = DEFAULT_CHANNELS + []


class AlertChannel(models.Model):
    _name = "alert.channel"
    _description = "Channels are used to alert to user"

    name = fields.Char()
    channel_code = fields.Char()
    contact_field = fields.Char(require=True)
    channel_default = fields.Boolean('Is Channel Alert Default', default=False)

    def get_status_email_channel(self, receiver, context):
        available_to_send = True

        email_to = receiver.email
        kpi_id = context.get('kpi_id')
        com_id = context.get('comp_info')['id']
        kpi_value = self.env['kpi.company.value'].search([
            ('kpi_id', '=', kpi_id),
            ('company_id', '=', com_id)
        ])
        currency_id = context.get('comp_info')['currency_id']
        unit_type = kpi_value.kpi_id.unit
        raw_value = kpi_value.value
        period_type = dict(kpi_value.kpi_id.periods_type).get(kpi_value.kpi_id.period_type)

        value = convert_value_with_unit_type(unit_type, raw_value, currency_id)
        gap_value_change = kpi_value.value - kpi_value.value_pre_period
        margin = convert_value_with_unit_type(unit_type, gap_value_change, currency_id)

        if email_to:
            context.update({
                'email_to': email_to,
                'kpi_value': value,
                'margin': margin,
                'gap_value_change': gap_value_change,
                'period_type': period_type
            })
        else:
            available_to_send = False
        return available_to_send

    def send_alert_via_email(self, context):
        return self._send_alert_email(context, 'dashboard_alert.kpi_alert_mail_template')

    def send_alert_via_alternate_email(self, context):
        self._send_alert_email(context, 'dashboard_alert.kpi_alert_mail_template')

    def _send_alert_email(self, context, template_external_id):
        try:
            base_context = self.env.context
            template_id = self.env.ref(template_external_id).id
            mail_template = self.env['mail.template'].browse(template_id)

            list_btn = context.get('list_btn')

            if len(list_btn):
                subject = context.get('subject')
                email_to = context.get('email_to')
                comp_info = context.get('comp_info')
                kpi_id_name = context.get('kpi_id_name')
                creator_name = context.get('creator_name')
                condition_info = context.get('condition_info')
                user_receive = context.get('user_receive')
                server_link = context.get('server_link')
                kpi_value = context.get('kpi_value')
                margin = context.get('margin')
                gap_value_change = context.get('gap_value_change')
                period_type = context.get('period_type')

                template = mail_template.sudo() \
                    .with_context(base_context, lang='en_US',
                                  template_type="follower",
                                  list_btn=list_btn,
                                  subject=subject,
                                  user_receive=user_receive,
                                  server_link=server_link,
                                  comp_info=comp_info,
                                  creator_name=creator_name,
                                  kpi_id_name=kpi_id_name,
                                  condition_info=condition_info,
                                  kpi_value=kpi_value,
                                  margin=margin,
                                  gap_value_change=gap_value_change,
                                  period_type=period_type
                                  )

                template.send_mail(self.id,
                                   force_send=True,
                                   raise_exception=False,
                                   email_values={
                                       'email_to': email_to,
                                       'subject': subject
                                   })
                return True
            else:
                _logger.warning("Can not generate URL to embed to email with alert which have subject is \"%s\" of "
                                "user %s" %
                                (self.subject, self.user_alert_id.name))
                return False
        except:
            _logger.warning("Some problem happen when send alert email")
            return False

    ########################################################
    # INITIAL DATA
    ########################################################
    @api.model
    def init_channel_data(self):
        for code, name in DEFAULT_CHANNELS:
            self.create({
                'channel_code': code,
                'name': name,
                'channel_default': True
            })
