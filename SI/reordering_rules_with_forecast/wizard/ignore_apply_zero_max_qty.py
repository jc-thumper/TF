# -*- coding: utf-8 -*-

import ast

from odoo import models, fields, api


class IgnoreApplyZeroNewMaxQty(models.TransientModel):
    _name = "ignore.apply.zero.new.max.qty"
    _description = "Ignore Apply Zero to Max Qty"

    message = fields.Text(default=lambda self: self.env.context.get('message'),
                          help="Message to show in popup confirmation window")

    def accept_confirmation(self):
        record_ids = ast.literal_eval(self.env.context.get('record_ids'))
        rrwf_ids = self.env['reordering.rules.with.forecast']\
            .sudo()\
            .search([('id', 'in', record_ids)])
        auto_generate_new_rr = bool(self.env.context.get("auto_generate_new_rr"))
        rrwf_ids.sudo().generate_new_reordering_rules(auto_generate_new_rr)

    def cancel_confirmation(self):
        record_ids = ast.literal_eval(self.env.context.get('record_ids'))
        rrwf_ids = self.env['reordering.rules.with.forecast'] \
            .sudo() \
            .search([('id', 'in', record_ids)])
        auto_generate_new_rr = bool(self.env.context.get("auto_generate_new_rr"))
        rrwf_ids.sudo().generate_new_reordering_rules(auto_generate_new_rr, allow_max_is_zero=True)
        return {'type': 'ir.actions.act_window_close'}

