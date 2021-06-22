# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import logging

from odoo import api, models, fields, modules, tools, _

_logger = logging.getLogger(__name__)


class InheritedResUsers(models.Model):
    _inherit = 'res.users'

    channel_info_ids = fields.One2many('user.channel.info',
                                       'user_id',
                                       compute='_compute_channel_info', store=True)

    # working_hours = fields.Many2many('range.time.info')
    time_zone = fields.Integer('Time zone', default=0)
    time_on_call = fields.Many2one('range.time.info')
    # mobile_sms_rec = fields.Char(string='Mobile Number Receive Alert', default=_default_mobile_sms_rec)
    channel_rec_mes_ids = fields.Many2many(related='partner_id.channel_rec_mes_ids', inherited=True, readonly=False)

    def __init__(self, pool, cr):
        """ Override of __init__ to add access rights on notification_email_send
            and alias fields. Access rights are disabled by default, but allowed
            on some specific fields defined in self.SELF_{READ/WRITE}ABLE_FIELDS.
        """
        init_res = super(InheritedResUsers, self).__init__(pool, cr)
        # duplicate list to avoid modifying the original reference
        type(self).SELF_WRITEABLE_FIELDS = list(self.SELF_WRITEABLE_FIELDS)
        type(self).SELF_WRITEABLE_FIELDS.extend(['channel_rec_mes_ids'])
        # duplicate list to avoid modifying the original reference
        type(self).SELF_READABLE_FIELDS = list(self.SELF_READABLE_FIELDS)
        type(self).SELF_READABLE_FIELDS.extend(['channel_rec_mes_ids'])
        return init_res

    ########################################################
    # COMPUTED FUNCTIONS
    ########################################################
    @api.depends('channel_rec_mes_ids')
    def _compute_channel_info(self):
        print('_compute_channel_info')
        modelUCI = self.env['user.channel.info']
        for user in self:
            channels = user.channel_rec_mes_ids.ids
            personal_channel_alert = modelUCI.search([('user_id', '=', user.id)])
            current_channel = personal_channel_alert.mapped(lambda channel: channel.channel_id.id)

            user_channel_info = []
            new_channel_alert_ids = list(set(channels) - set(current_channel))
            exist_channel_alert_ids = list(set(channels) - set(new_channel_alert_ids))
            old_channel_alert_ids = list(set(current_channel) - set(exist_channel_alert_ids))

            # Delete old channel
            old_user_channel_alert_ids = personal_channel_alert. \
                filtered(lambda channel: channel.channel_id.id in old_channel_alert_ids).ids
            for old_channel in old_user_channel_alert_ids:
                user_channel_info.append((3, old_channel))

            # Update relation to exiting channel
            exist_user_channel_alert_ids = personal_channel_alert. \
                filtered(lambda channel: channel.channel_id.id in exist_channel_alert_ids).ids
            for exist_id in exist_user_channel_alert_ids:
                user_channel_info.append((4, exist_id))

            # Create new item and make the relation
            for new_channel_id in new_channel_alert_ids:
                user_channel_info.append((0, 0, {
                    'channel_id': new_channel_id,
                    'user_id': user.id
                }))
            user.channel_info_ids = user_channel_info
            self.env.cr.commit()

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    def _get_action_partner_contact(self, partner, miss_channels=[]):
        ctx = {}
        for channel in miss_channels:
            ctx[channel] = True
        view_id = self.env.ref('dashboard_alert.view_contact_partner_info_form').id
        model = 'res.partner'
        res = {
            'name': _('Contact Information'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': model,
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'context': ctx,
            'res_id': partner.id,
            'target': 'new'
        }
        return res

    ########################################################
    # BUTTON EVENT
    ########################################################
    def show_contact_form(self):
        partner = self.env.user.partner_id
        channels_contact = self.env['alert.channel'].search([]).mapped('channel_code')
        return self._get_action_partner_contact(partner, channels_contact)

    def preference_save(self):
        res = super(InheritedResUsers, self).preference_save()
        for user in self:
            partner = user.partner_id
            if partner:
                miss_channels = []
                for channel in user.channel_rec_mes_ids:
                    value = getattr(partner, channel.contact_field, '')
                    if not value:
                        miss_channels.append(channel.channel_code)
                if len(miss_channels):
                    res = self._get_action_partner_contact(partner, miss_channels)
            else:
                _logger.warning("Do not have partner corresponding partner for user has id %s" % user.id)
        return res

    ########################################################
    # INITIAL DATA
    ########################################################
    @api.model
    def init_default_channel(self):
        users = self.search([])
        default_channel_ids = self.env['alert.channel'].search([('channel_default', '=', True)]).ids
        default_val = [(6, 0, default_channel_ids)]
        for user in users:
            user.write({
                'channel_rec_mes_ids': default_val
            })
