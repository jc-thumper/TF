# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, models, fields, modules, tools, _


class UserChannelInfo(models.Model):
    _name = "user.channel.info"
    _description = "Group of alerts"

    channel_id = fields.Many2one('alert.channel')
    time_receive = fields.Char()
    group_alert_rec_id = fields.Many2one('group.alert')
    user_id = fields.Many2one('res.users')
