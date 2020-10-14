# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    user_ids = fields.Many2many('res.users', string="Allowed Users")


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
