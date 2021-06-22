# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, models, fields, modules, tools, _

MINUTES = "minutes"
SECONDS = "seconds"
HOURS = "hours"


class AlertSetting(models.Model):
    _name = "alert.setting"
    _description = "General Alert Setting"

    list_time_frequency = [
        (SECONDS, 'Seconds'),
        (MINUTES, 'Minutes'),
        (HOURS, 'Hours'),
    ]

    frequency_update = fields.Selection(list_time_frequency, string='Frequency Update',
                                        default=SECONDS)
    interval_time_size = fields.Integer('Interval Time Update')
    delay_notifications = fields.Boolean('Delay Notifications', default=False)
    times_reach_to_condition = fields.Integer()
    num_seconds = fields.Integer()
