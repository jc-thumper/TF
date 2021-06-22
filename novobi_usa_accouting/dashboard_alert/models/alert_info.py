# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import logging

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.addons.account_dashboard.models.kpi_journal import PERCENTAGE, CURRENCY
from odoo import api, models, fields, modules, tools, _
from odoo.tools.safe_eval import safe_eval
from lxml import etree

_logger = logging.getLogger(__name__)

# Operator for condition used to check and send notify
GREATER_THAN = '>'
LESS_THAN = '<'
GREATER_EQUAL_THAN = '>='
LESS_EQUAL_THAN = '<='

FIRST_TIME = 'first_time'
ALWAYS = 'always'
HOURLY = 'hourly'
DAILY = 'daily'
WEEKLY = 'weekly'
MONTHLY = 'monthly'

# Delete status
DELETE_SUCCESS = 'del_success'
DELETE_ASSIGNED_ALERT = 'del_assigned'
DELETE_MIX = 'del_mix'
DELETE_FAIL = 'del_fail'

IS_CREATOR = 'is_creator'
IS_NOT_RECIPIENT = 'is_not_recipient'
IS_NOT_CREATOR = 'in_not_creator'


class AlertInfo(models.Model):
    _name = "alert.info"
    _description = "Alert Information"

    def _kpi_id_default_get(self):
        kpi_id = self._context.get('kpi_id')
        if kpi_id:
            return kpi_id
        else:
            return None

    def _company_id_default_get(self):
        return self.env.user.company_id.id

    def _default_previous_value(self):
        return 0

    def _default_recipient(self):
        return self.env.user

    list_conditions = [
        (GREATER_THAN, 'Greater Than'),
        (GREATER_EQUAL_THAN, 'Greater Equal Than'),
        (LESS_THAN, 'Less Than'),
        (LESS_EQUAL_THAN, 'Less Equal Than')
    ]

    list_options_creator = [
        (IS_CREATOR, 'Is Creator and Recipient'),
        (IS_NOT_RECIPIENT, 'Is Creator and Not Recipient'),
        (IS_NOT_CREATOR, 'Is Recipient')
    ]

    list_time_send = [
        (FIRST_TIME, "Once at the first time it's true"),
        (ALWAYS, 'Always reach to condition'),
        (HOURLY, 'Hourly at most'),
        (DAILY, 'Daily at most'),
        (WEEKLY, 'Weekly at most'),
        (MONTHLY, 'Monthly at most'),
    ]

    kpi_id = fields.Many2one('kpi.journal',
                             require=True, default=_kpi_id_default_get)
    condition = fields.Selection(list_conditions, require=True, default=GREATER_THAN,
                                 help="Type of condition used to compare with KPI value")
    value = fields.Float('Threshold', require=True,
                         help="The alert will sent you when KPI reached to the condition with this threshold")
    formatted_value = fields.Char(string='Threshold', compute='_compute_formatted_value')
    previous_value = fields.Float("Previous Value", require=True, store=True, compute='_compute_previous_value')

    subject = fields.Char('Subject', require=True,
                          help="This text will show as the Subject of an "
                               "Email/Notification when you receive and alert")
    company_id = fields.Many2one('res.company', require=True, default=_company_id_default_get)
    group_id = fields.Many2one('group.alerts')
    recipient_ids = fields.Many2many('res.users',
                                     'alert_info_res_users_rel',
                                     'alert_info_id',
                                     'user_id', string='Recipients', default=_default_recipient)
    group_rec_ids = fields.Many2many('res.groups',
                                     'alert_info_res_groups_rel',
                                     'alert_info_id',
                                     'group_id', string='Group Recipients')
    personal_alert = fields.One2many('personalized.alert.info',
                                     'alert_info_id',
                                     string='Personal Alert',
                                     compute='_compute_personal_alert', store=True)
    # alert_category_ids = fields.Many2many('alert_category')
    number_notify_receivable = fields.Integer('Number Notify Receivable', default=1)
    cond_time_send = fields.Selection(list_time_send, 'Time to Send The Alert', require=True, default=FIRST_TIME)
    will_cumulative = fields.Boolean()
    cumulative_value = fields.Float()
    times_reach_to_condition = fields.Integer(default=0, compute='_compute_previous_value', store=True)
    creator_id = fields.Many2one('res.users', require=True, default=lambda self: self.env.user)
    nearest_right = fields.Datetime("Last time check Condition", default=False, store=True)
    last_send = fields.Datetime(default=False, store=True)

    is_creator = fields.Selection(list_options_creator, compute='_compute_is_creator',
                                  search='_search_is_creator', store=False, default=True)
    self_active = fields.Boolean('Subscribed', compute='_compute_self_active',
                                 inverse='_inverse_self_active', search='_search_self_active', store=False,
                                 default=True)

    ########################################################
    # STANDARD FUNCTIONS
    ########################################################
    def unlink(self):
        self.clear_caches()
        list_personal_alert_id = []
        for alert in self:
            list_personal_alert_id += alert.personal_alert.ids
        if list_personal_alert_id:
            self.env['personalized.alert.info'].sudo().search([
                '|', ('active', '=', True), ('active', '=', False),
                ('id', 'in', list_personal_alert_id)
            ]).unlink()
        return super(AlertInfo, self).unlink()

    def write(self, values):
        res = super(AlertInfo, self).write(values)
        nearest_right = values.get('nearest_right', None)
        times_reach_to_condition = values.get('times_reach_to_condition', None)
        change_val_status = False
        cond_alert = False

        if isinstance(nearest_right, datetime):
            cond_alert = True
            if isinstance(times_reach_to_condition, int):
                change_val_status = True

        for alert in self:

            if cond_alert:
                if alert.get_status_lunch_alert(change_val_status):
                    alert.send_alert()
                    alert.write({"last_send": nearest_right})

        return res

    ########################################################
    # COMPUTED FUNCTIONS
    ########################################################
    @api.depends('condition', 'value', 'cond_time_send')
    def _compute_previous_value(self):
        for alert in self:
            threshold = alert.value
            condition = alert.condition
            pre_value_default = threshold + 1

            if safe_eval(str(pre_value_default) + condition + str(threshold)):
                pre_value_default = threshold - 1

            alert.previous_value = pre_value_default
            alert.times_reach_to_condition = 0

    def _compute_formatted_value(self):
        format_value = self.env['kpi.journal'].format_number_type
        for alert in self:
            alert.formatted_value, _ = format_value(alert.value, alert.kpi_id.unit)

    def _compute_self_active(self):
        uid = self.env.user.id
        alert_info_dict = dict(self.env['personalized.alert.info'].sudo().search([
            '|', ('active', '=', True), ('active', '=', False),
            ('user_alert_id', '=', uid)
        ]).mapped(lambda alert: (alert.alert_info_id.id, alert)))
        for alert in self:
            person_alert_info = alert_info_dict.get(alert.id)
            if person_alert_info:
                alert.self_active = person_alert_info.active

    def _inverse_self_active(self):
        uid = self.env.user.id
        model_PAI = self.env['personalized.alert.info'].sudo().search([
            '|', ('active', '=', True), ('active', '=', False),
            ('user_alert_id', '=', uid)
        ])
        for alert in self:
            person_alert_info = model_PAI.filtered(lambda p_alert: p_alert.alert_info_id.id == alert.id)
            person_alert_info.write({
                'active': alert.self_active
            })

    def _search_self_active(self, operator, value):
        cur_user = self.env.user
        self_alert = self.env['personalized.alert.info'].sudo().search([
            ('user_alert_id', '=', cur_user.id),
            ('active', operator, value)
        ])
        alert_ids = self_alert.mapped(lambda alert: alert.alert_info_id.id)
        return [('id', 'in', alert_ids)]

    def _search_is_creator(self, operator, value):
        if operator not in ('=', '!=', 'in'):
            raise ValueError('Invalid operator: %s' % (operator,))
        cur_user = self.env.user
        if value not in (IS_CREATOR, IS_NOT_RECIPIENT):
            operator = operator == '=' and '!=' or '='
        self_alert = self.sudo().search([
            ('creator_id', operator, cur_user.id)
        ])
        return [('id', 'in', self_alert.ids)]

    def _compute_is_creator(self):
        cur_user = self.env.user
        for alert in self:
            if cur_user.id == alert.creator_id.id:
                if cur_user.id in alert.recipient_ids.ids:
                    alert.is_creator = IS_CREATOR
                else:
                    alert.is_creator = IS_NOT_RECIPIENT
            else:
                alert.is_creator = IS_NOT_CREATOR

    # @api.depends('times_reach_to_condition')
    # def _compute_last_send(self):
    #     print("_compute_last_send")
    #     for alert in self:
    #         if alert.get_status_lunch_alert():
    #             alert.send_alert()
    #
    #             alert.last_send = fields.datetime.now()
    #         alert.last_send = alert.last_send

    @api.depends('recipient_ids')
    def _compute_personal_alert(self):
        print('_compute_personal_alert')
        modelPAI = self.env['personalized.alert.info']
        for alert in self:
            recipients = alert.recipient_ids.ids
            personal_alert = modelPAI.sudo().search(['|', ('active', '=', True), ('active', '=', False),
                                                     ('alert_info_id', '=', alert.id)])
            current_users = personal_alert.mapped(lambda person: person.user_alert_id.id)

            # Update new data for personal_alert base on temp var "personal_alert_update_info"
            personal_alert_update_info = []
            new_personal_alert_ids = list(set(recipients) - set(current_users))
            exist_personal_alert_ids = list(set(recipients) - set(new_personal_alert_ids))
            old_channel_alert_ids = list(set(current_users) - set(exist_personal_alert_ids))

            # Delete old channel
            old_personal_alerts = personal_alert \
                .filtered(lambda person: person.user_alert_id.id in old_channel_alert_ids)
            for old_personal_alert in old_personal_alerts:
                personal_alert_update_info.append((3, old_personal_alert.id))
                old_personal_alert.unlink()

            # Update relation to exiting channel
            exist_personal_alert = personal_alert. \
                filtered(lambda person: person.user_alert_id.id in exist_personal_alert_ids)
            for exist_id in exist_personal_alert.ids:
                personal_alert_update_info.append((4, exist_id))

            # Create new item and make the relation
            for user_id in new_personal_alert_ids:
                personal_alert_update_info.append((0, 0, {
                    'user_alert_id': user_id,
                    'alert_info_id': alert.id
                }))
            alert.personal_alert = personal_alert_update_info
            self.env.cr.commit()

    ########################################################
    # BUTTON CLICK
    ########################################################
    def toggle_self_active(self):
        for alert in self:
            alert.self_active = not alert.self_active

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    def send_alert(self):
        """ Function process send alert to each recipients

        :return:
        """
        for alert in self:
            recipients = alert.recipient_ids.ids
            personal_alerts = self.env['personalized.alert.info'].search([
                ('user_alert_id', 'in', recipients),
                ('alert_info_id', '=', alert.id),
            ])
            if personal_alerts:
                for person in personal_alerts:
                    if person.active:
                        person.action_send_alert()

            alert.last_send = fields.datetime.now()

    @api.model
    def get_status_lunch_alert(self, change_val_status):
        """ Function return a flat used to confirm a alert will send.
        It will satisfy with time to send condition.

        :return:
        """
        will_lunch = False
        if self.cond_time_send == FIRST_TIME:
            will_lunch = self.times_reach_to_condition == 1 and change_val_status
        elif self.cond_time_send == ALWAYS:
            will_lunch = self.times_reach_to_condition >= 1 and change_val_status
        elif self.cond_time_send == HOURLY:
            hours = relativedelta(fields.Datetime.now(), self.last_send).hours
            will_lunch = self.times_reach_to_condition >= 1 and (hours >= 1 or not self.last_send)
        elif self.cond_time_send == DAILY:
            days = relativedelta(fields.Datetime.now(), self.last_send).days
            will_lunch = self.times_reach_to_condition >= 1 and (days >= 1 or not self.last_send)
        elif self.cond_time_send == WEEKLY:
            days = relativedelta(fields.Datetime.now(), self.last_send).days
            will_lunch = self.times_reach_to_condition >= 1 and (days >= 7 or not self.last_send)
        elif self.cond_time_send == MONTHLY:
            months = relativedelta(fields.Datetime.now(), self.last_send).months
            will_lunch = self.times_reach_to_condition >= 1 and (months >= 1 or not self.last_send)

        return will_lunch

    ########################################################
    # API FUNCTION
    ########################################################
    @api.model
    def call_create_kpi_alert(self, kpi_id, res_id):
        kpi = self.env['kpi.journal'].search([
            ('id', '=', kpi_id)
        ])
        widget_unit = ''
        if kpi.unit == PERCENTAGE:
            widget_unit = 'percentage'
        elif kpi.unit == CURRENCY:
            widget_unit = 'monetary'
        form_name = _('Alert for ' + kpi.name)
        result = {}
        action = {
            'type': 'ir.actions.act_window',
            'name': form_name,
            'res_id': res_id,
            'res_model': 'alert.info',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'views': [(self.env.ref('dashboard_alert.alert_info_popup_form').id, 'form')],
            'flags': {'form': {'action_buttons': True, 'options': {'mode': 'edit'}}},
            'context': {'kpi_id': kpi_id, 'widget_unit': widget_unit}
        }

        result['action'] = action
        result['res'] = 1
        return result

    @api.model
    def call_delete_kpi_alerts(self, alert_ids, still_delete_self_alert=False):
        result = {}
        try:
            alerts = self.search([('id', 'in', alert_ids)])
            self_create_alerts = alerts.filtered(lambda alert: alert.creator_id.id == self.env.user.id)
            assigned_alerts = alerts.filtered(lambda alert: alert.creator_id.id != self.env.user.id)
            if len(assigned_alerts) and not still_delete_self_alert:
                creators = assigned_alerts.mapped(lambda alert: alert.creator_id.partner_id.name)
                creators_name = list(set(creators))

                result['mess'] = _('The requested delete operation cannot be completed '
                                   'due to User %s\'s own this Alert.' % (', '.join(creators_name)))
                if len(self_create_alerts):
                    result['status'] = DELETE_MIX
                else:
                    result['status'] = DELETE_ASSIGNED_ALERT
            else:
                self_create_alerts.unlink()
                result['status'] = DELETE_SUCCESS
        except:
            result['status'] = DELETE_FAIL
            result['mess'] = _('Some problems were happening when this record deleted')
        return result
    
    def name_get(self):
        result = []
        for alert in self:
            result.append((alert.id, alert.subject))
        return result
