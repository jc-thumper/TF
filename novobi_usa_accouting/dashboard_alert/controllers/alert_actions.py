# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.

import ast
import logging
import time
from datetime import datetime

import werkzeug
from dateutil.relativedelta import relativedelta

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from ..utils.utils import is_equal
from ..models.personalized_alert_info import SUBSCRIBE, UNSUBSCRIBE
from odoo import http, _, fields
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

SNOOZE_OPTIONS = [
                {'name': '1 Minute', 'value': 1, 'default': True},
                {'name': '5 Minutes', 'value': 5, 'default': False},
                {'name': '15 Minutes', 'value': 15, 'default': False},
                {'name': '30 Minutes', 'value': 30, 'default': False},
                {'name': '1 Hour', 'value': 60, 'default': False},
                {'name': '2 Hours', 'value': 120, 'default': False},
                {'name': '1 Day', 'value': 1320, 'default': False},
                {'name': '1 Week', 'value': 9240, 'default': False},
            ]


class ActionError(Exception):
    pass


class AlertActions(http.Controller):
    @http.route('/web/dashboard_alert/subscribe/', type='http', auth='public', website=True, sitemap=False)
    def get_subscribe_view(self, *args, **kw):
        qcontext = self.get_action_qcontext()
        qcontext['title'] = _("Unsubscribe")

        if 'error' not in qcontext:
            # default status is being subscribe.
            qcontext['status'] = UNSUBSCRIBE

            current_status = self._get_subscribe_status_alert(qcontext)
            if isinstance(current_status, bool) and 'error' not in qcontext:
                subscribe_status = qcontext.get('status') == SUBSCRIBE

                # symbol ^ mean XOR
                same_status = not(current_status ^ subscribe_status)
                if same_status:
                    qcontext['status'] = UNSUBSCRIBE if current_status else SUBSCRIBE

                if qcontext['status'] == UNSUBSCRIBE:
                    personal_alert_info = self.get_alert_info(qcontext)
                    if personal_alert_info:
                        qcontext['mess'] = _('If you do not want to receive this announcement from the KPI Alert '
                                             '<b>%s</b> anymore in the future, please click on Unsubscribe.' %
                                             (personal_alert_info['subject'], ))

        if qcontext.get('token') and qcontext.get('disable'):
            request.env['personalized.alert.info'].sudo().search()

        response = request.render('dashboard_alert.unsubscribe_alert', qcontext)
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @http.route('/web/dashboard_alert/change_subscribe_status/', type='json',
                auth='none', sitemap=False)
    def change_subscribe_status(self, *args, **kw):
        """ API support user change the subscribe or not some kpi via the email

        :param args:
        :param kw: need at least information of token and status want to
        change to with structure:
        {
            'token': abcABC123
            'status': subscribe/unsubscribe
        }
        :return: json
        """
        qcontext = self.get_action_qcontext()
        response = {'token': qcontext['token']}

        if 'error' not in qcontext:
            current_status = self._get_subscribe_status_alert(qcontext)
            if isinstance(current_status, bool) and 'error' not in qcontext:
                subscribe_status = qcontext.get('status') == SUBSCRIBE
                personal_alert_info = self.get_alert_info(qcontext)
                change_status = request.env['personalized.alert.info'].sudo() \
                    .change_subscribe_status_alert(subscribe_status, qcontext.get('token'))
                response['status'] = UNSUBSCRIBE if subscribe_status else SUBSCRIBE

                if change_status:
                    if personal_alert_info:
                        self.change_token(qcontext.get('token'))
                        response['mess'] = _('Thank you, you have been Unsubscribed from %s' %
                                             personal_alert_info['detail'])
                else:
                    qcontext['error'] = _("Have some problem when change status")

        if 'error' in qcontext:
            response['error'] = qcontext['error']

        return response

    @http.route('/web/dashboard_alert/snooze/', type='http', auth='public', website=True, sitemap=False)
    def get_snooze_view(self, *args, **kw):
        qcontext = self.get_action_qcontext()
        qcontext['title'] = _("Snooze")

        if 'error' not in qcontext:
            qcontext['time_options'] = SNOOZE_OPTIONS
            personal_alert_info = self.get_alert_info(qcontext)
            if personal_alert_info:
                if personal_alert_info['active']:
                    qcontext['subject'] = personal_alert_info['subject']
                    qcontext['detail'] = personal_alert_info['detail']
                else:
                    qcontext['error'] = _('This alert has been unsubscribed')
            else:
                qcontext['error'] = _('This alert is not available')

        if qcontext.get('token') and qcontext.get('disable'):
            request.env['personalized.alert.info'].sudo().search()

        response = request.render('dashboard_alert.snooze_alert', qcontext)
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @http.route('/web/dashboard_alert/update_time_sent_again/', type='json',
                auth='none', sitemap=False)
    def update_time_sent_again(self, *args, **kw):
        """ API support user update the number of minutes snooze

        :param args:
        :param kw: need at least information of token and status want to
        change to with structure:
        {
            'change_success': True/False
        }
        :return: json
        """
        qcontext = self.get_action_qcontext()
        response = {'change_success': False}

        if 'error' not in qcontext:
            personal_alert_info = request.env['action.session'].sudo() \
                .get_corresponding_data(qcontext.get('token'))
            if personal_alert_info:
                if personal_alert_info.active:
                    try:
                        minutes_sent = int(qcontext['minutes_sent'])
                    except:
                        minutes_sent = None

                    if isinstance(minutes_sent, int):
                        current = fields.Datetime.now()
                        time_resend = current + relativedelta(minutes=minutes_sent)

                        personal_alert_info.write({'time_sent_again': time_resend})
                        format_time_receive = time_resend.strftime(DEFAULT_SERVER_DATETIME_FORMAT) + ' UTC'

                        new_token = self.change_token(qcontext.get('token'))

                        response.update({
                            'change_success': True,
                            'mess': _('The Alert will re-send notification at '),
                            'time_receive': format_time_receive,
                            'token': new_token
                        })
                    else:
                        response['error'] = _('Minutes Snooze have to a Integer Number')
                else:
                    response['error'] = _('You can not snooze this alert because it has just unsubscribed')
            else:
                response['error'] = _('This alert is not available')
        else:
            response['error'] = qcontext['error']

        return response

    @http.route('/web/dashboard_alert/more_settings/', type='http', auth='public', website=True, sitemap=False)
    def get_more_settings_view(self, *args, **kw):
        qcontext = self.get_action_qcontext()
        qcontext['title'] = _("More Settings")

        if 'error' not in qcontext:
            personal_alert_info = self.get_alert_detail_setting(qcontext)
            if personal_alert_info:
                qcontext.update(personal_alert_info)
            elif personal_alert_info is not None:
                qcontext['error'] = _('This alert is not exist')
            else:
                qcontext['error'] = _('This alert is not available')

        if qcontext.get('token') and qcontext.get('disable'):
            request.env['personalized.alert.info'].sudo().search()

        response = request.render('dashboard_alert.alert_more_settings', qcontext)
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @http.route('/web/dashboard_alert/update_setting/', type='json',
                auth='none', sitemap=False)
    def update_setting(self, *args, **kw):
        """ API support user update general setting for the alert

        :param args:
        :param kw: need at least information of token and status want to
        change to with structure:
        {
            'change_success': True/False
        }
        :return: json
        """
        qcontext = self.get_action_qcontext()
        response = {
            'token': qcontext['token']
        }

        if 'error' not in qcontext:
            personal_alert_info = request.env['action.session'].sudo() \
                .get_corresponding_data(qcontext.get('token'))
            if personal_alert_info:
                try:
                    if qcontext['threshold'] == '':
                        threshold = 0.0
                    else:
                        threshold = float(qcontext['threshold'])
                except:
                    threshold = None

                if isinstance(threshold, float):

                    alert_info = personal_alert_info.alert_info_id

                    if qcontext['direct_update'] or personal_alert_info.active:
                        try:
                            update_info = {}
                            if not is_equal(threshold, alert_info.value):
                                update_info['value'] = threshold

                            if not qcontext['condition'] == alert_info.condition:
                                update_info['condition'] = qcontext['condition']

                            if not qcontext['time_alert'] == alert_info.cond_time_send:
                                update_info['cond_time_send'] = qcontext['time_alert']

                            if not qcontext['subject'] == alert_info.subject:
                                update_info['subject'] = qcontext['subject']

                            if update_info:
                                alert_info.write(update_info)

                            self.change_token(qcontext.get('token'))
                            response['re_update'] = False
                            response['mess'] = _("Updated Successfully!")
                        except:
                            response['re_update'] = True
                            response['mess'] = _('Update to database fail, Do you want to update again?')
                    else:
                        response['re_update'] = True
                        response['mess'] = _("This alert has just unsubscribed. Are you sure you want to continue?")
                else:
                    response['error'] = _('Threshold value have to a Integer Number')
            else:
                response['error'] = _('This alert is not available')
        else:
            response['error'] = qcontext['error']

        return response

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    @staticmethod
    def change_token(token):
        action_info = request.env['action.session'].sudo() \
            .search([('token', '=', token)])
        return action_info.update_new_token()

    @staticmethod
    def get_alert_info(context):
        """

        :param context:
        :return:
        """
        personal_alert = request.env['action.session'].sudo() \
            .get_corresponding_data(context.get('token'))
        if personal_alert:
            personal_alert_info_dict = personal_alert.get_alert_personal_info()
            personal_alert_info_dict.update({
                'active': personal_alert.active
            })
        else:
            personal_alert_info_dict = None
        return personal_alert_info_dict

    @staticmethod
    def get_alert_detail_setting(context):
        """

        :param context:
        :return:
        """
        personal_alert = request.env['action.session'].sudo() \
            .get_corresponding_data(context.get('token'))
        personal_alert_info_dict = {}
        if personal_alert:
            alert = personal_alert.alert_info_id
            list_cond = []
            for value, name in alert.list_conditions:
                list_cond.append({
                    'val': value,
                    'name': name,
                    'default': value == personal_alert.condition
                })

            list_time_send = []
            for value, name in alert.list_time_send:
                list_time_send.append({
                    'val': value,
                    'name': name,
                    'default': value == alert.cond_time_send
                })

            personal_alert_info_dict.update({
                'active': personal_alert.active,
                'cond_options': list_cond,
                'subject': personal_alert.subject,
                'cond_time_send': list_time_send,
                'threshold': personal_alert.value
            })

        else:
            personal_alert_info_dict = None
        return personal_alert_info_dict

    @staticmethod
    def _get_subscribe_status_alert(context):
        current_status = None
        if context.get('status'):
            if context.get('status') in (SUBSCRIBE, UNSUBSCRIBE):
                action = request.env['action.session'].sudo().search([('token', '=', context.get('token'))])
                if action:
                    item_info = dict(ast.literal_eval(action.item_data))
                    personal_alert = request.env['personalized.alert.info'].sudo()\
                        .search([('id', '=', item_info['id']), '|', ('active', '=', True), ('active', '=', False)])
                    if personal_alert:
                        current_status = personal_alert.active
                        if not current_status:
                            current_status = None
                            context['error'] = _("This alert has been unsubscribed")
                    else:
                        context['error'] = _("This alert is not available")
                else:
                    context['error'] = _("Your request use invalid/expire token")
            else:
                context['error'] = _("The system just have two type of status is 'Subscribe' and 'Unsubscribe'")
        else:
            context['error'] = _("Do not exist the status which you want to change")
        return current_status

    @staticmethod
    def check_valid_token(token):
        cur_time = datetime.now()
        session = request.env['action.session'].sudo() \
            .search([('token', '=', token), ('expiration', '>=', cur_time)])
        if session:
            return session.item_data
        else:
            return False

    @staticmethod
    def get_action_qcontext():
        """ Shared helper returning the rendering context for signup and reset password """
        qcontext = request.params.copy()
        if qcontext.get('token'):
            try:
                token_infos = request.env['action.session'].sudo()\
                    .search([('token', '=', qcontext.get('token'))])
                if not token_infos:
                    qcontext['error'] = _("Invalid token")
                else:
                    current = datetime.now()
                    if token_infos.expiration and token_infos.expiration < current:
                        qcontext['error'] = _("Sorry, your token expired!")
            except():
                qcontext['error'] = _("Invalid token")
                qcontext['invalid_token'] = True
        else:
            qcontext['error'] = _("Your request is missing the token")
        return qcontext
