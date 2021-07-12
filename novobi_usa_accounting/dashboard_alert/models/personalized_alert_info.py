# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import ast
import logging

import werkzeug.urls

from odoo.addons.account_dashboard.utils.utils import convert_value_with_unit_type
from ..utils.utils import _get_url_from_menu
from odoo import api, models, fields, modules, tools, exceptions, _

_logger = logging.getLogger(__name__)

SUBSCRIBE = 'subscribe'
UNSUBSCRIBE = 'unsubscribe'
SNOOZE = 'snooze'
MORE_SETTINGS = 'more_settings'

BUTTONS_NAME = [
    (UNSUBSCRIBE, 'Unsubscribe'),
    (SNOOZE, 'Snooze'),
    (MORE_SETTINGS, 'More Settings'),
]

BUTTONS_NAME_DICT = dict(BUTTONS_NAME)


class PersonalizedAlertInfo(models.Model):
    _name = "personalized.alert.info"
    _description = "Alert Information for each User"

    user_alert_id = fields.Many2one('res.users', require=True, readonly=True)
    time_sent_again = fields.Datetime('Minutes Snooze', default=False)
    alert_info_id = fields.Many2one('alert.info', require=True)
    active = fields.Boolean('Subscribed', default=True)

    subject = fields.Char(related='alert_info_id.subject', store=False)
    condition = fields.Selection(related='alert_info_id.condition', store=False, readonly=True)
    value = fields.Float(related='alert_info_id.value', store=False, readonly=True)
    creator_id = fields.Many2one(related='alert_info_id.creator_id', store=False, readonly=True)
    is_creator = fields.Boolean(compute='_compute_current_user_id', store=False)

    def write(self, values):
        return super(PersonalizedAlertInfo, self).write(values)

    ########################################################
    # COMPUTED FUNCTIONS
    ########################################################
    def _compute_current_user_id(self):
        self.is_creator = self.env.user.id == self.creator_id.id

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    def get_alert_personal_info(self):
        alert_info = self.alert_info_id
        detail_alert_info = '%s  %s' % (alert_info.kpi_id.name, self.get_condition(), )
        info = {
            'subject': self.subject,
            'detail': detail_alert_info
        }
        return info

    def get_condition(self):
        """ Function return string is condition of alert with format "operator_by_letter value_with_unit"

        :return:
        """
        alert_info = self.alert_info_id
        condition_operator = dict(alert_info.list_conditions)[alert_info.condition]
        formatted_alert_value = convert_value_with_unit_type(alert_info.kpi_id.unit,
                                                             alert_info.value,
                                                             alert_info.company_id.currency_id)
        condition_info = "%s %s" % (condition_operator, formatted_alert_value, )
        return condition_info

    def _get_button_info(self, model, button_key):
        result = {}

        btn_name = BUTTONS_NAME_DICT.get(button_key)
        if btn_name:
            url = model.get_url(button_key, self)
            if url:
                result.update({
                    'name': btn_name,
                    'url': url,
                    'code': button_key
                })
        return result

    def _get_context_alert(self):
        ctx_result = {}
        modelAS = self.env['action.session']

        list_btn = []

        for btn, _ in BUTTONS_NAME:
            if btn != MORE_SETTINGS or self.creator_id.id == self.user_alert_id.id:
                list_btn.append(self._get_button_info(modelAS, btn))

        alert_info = self.alert_info_id
        comp_info = alert_info.company_id
        condition_info = self.get_condition()
        server_link = _get_url_from_menu(context=self, menu_external_id='account_dashboard.menu_account_dashboard')

        ctx_result.update({
            'list_btn': list_btn,
            'user_receive': self.user_alert_id.name,
            'subject': alert_info.subject,
            'creator_name': self.creator_id.name,
            'kpi_id_name': alert_info.kpi_id.name,
            'kpi_id': alert_info.kpi_id.id,
            'condition_info': condition_info,
            'server_link': server_link,
            'comp_info': dict(id=comp_info.id, currency_id=comp_info.currency_id, name=comp_info.name,
                              phone=comp_info.phone, email=comp_info.email, website=comp_info.website)
        })
        return ctx_result

    @api.model
    def action_send_alert(self):
        context = self._get_context_alert()

        u_channels = self.user_alert_id.channel_info_ids

        for u_channel in u_channels:
            send_alert_status = True
            channel = u_channel.channel_id
            channel_name = channel.name
            channel_code = channel.channel_code
            if hasattr(channel, 'send_alert_via_%s' % channel_code):
                func = getattr(channel, 'send_alert_via_%s' % channel_code)
                extend_context = context.copy()

                if hasattr(channel, 'get_status_%s_channel' % channel_code):
                    status_func = getattr(channel, 'get_status_%s_channel' % channel_code)
                    send_alert_status = status_func(self.user_alert_id, extend_context)

                if send_alert_status:
                    res_alert = func(extend_context)
                if not res_alert:
                    _logger.warning("Can not sent alert for %s via %s" %
                                    (self.creator_id.name, channel_name,))
            else:
                _logger.warning('Do not exist channel %s for user %s' % (channel_name, self.user_alert_id.name,))

    @api.model
    def change_subscribe_status_alert(self, status, token=None):
        change_status = False
        if token:
            action = self.env['action.session'].sudo().search([('token', '=', token)])
        else:
            action = self

        if action:
            try:
                item_info = dict(ast.literal_eval(action.item_data))
                personal_alert = self.sudo().search([('active', '=', not status), ('id', '=', item_info['id'])])
                personal_alert.write({'active': status})
                change_status = True
            except:
                _logger.error("Change status with token %s to status '%s' is fail" % (token, status))
        return change_status

    @api.model
    def gen_unsubscribe_url(self, base_url, token):
        # the parameters to encode for the query
        query = dict(db=self.env.cr.dbname)

        query['token'] = token

        url = werkzeug.urls.url_join(base_url, "/web/dashboard_alert/%s?%s" %
                                     (SUBSCRIBE, werkzeug.urls.url_encode(query),))
        return url

    @api.model
    def gen_snooze_url(self, base_url, token):
        # the parameters to encode for the query
        query = dict(db=self.env.cr.dbname)

        query['token'] = token

        url = werkzeug.urls.url_join(base_url,
                                     "/web/dashboard_alert/%s?%s" % (SNOOZE, werkzeug.urls.url_encode(query),))
        return url

    @api.model
    def gen_more_settings_url(self, base_url, token):
        # the parameters to encode for the query
        query = dict(db=self.env.cr.dbname)

        query['token'] = token

        url = werkzeug.urls.url_join(base_url,
                                     "/web/dashboard_alert/%s?%s" % (MORE_SETTINGS, werkzeug.urls.url_encode(query),))
        return url

    ########################################################
    # CRON JOBS
    ########################################################
    def _automated_updates_minute_snooze_cron(self):
        snooze_items = self.search([('time_sent_again', '<=', fields.Datetime.now())])
        for item in snooze_items:
            snooze_items.write({'time_sent_again': False})
            item.action_send_alert()
