# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, models, fields, modules, tools, _


class GroupAlerts(models.Model):
    _name = "group.alerts"
    _description = "Group of alerts"

    name = fields.Char()
    priority = fields.Integer()
