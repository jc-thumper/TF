# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, models, fields, modules, tools, _


class AlertCategory(models.Model):
    _name = "alert.category"
    _description = "Category of Alert"

    name = fields.Char('Alert Category')
    description = fields.Char('Description')

