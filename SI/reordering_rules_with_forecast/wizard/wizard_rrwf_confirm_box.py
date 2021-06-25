# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import ast


class WizardRRwFConfirmBox(models.TransientModel):
    _name = "wizard.rrwf.confirm.box"
    _description = "Reordering Rules with Forecasting Confirm Box"

    # store message to show in a popup confirmation window
    message = fields.Text(default=lambda self: self.env.context.get('message'))

    auto_generate_new_rr = fields.Boolean(string="Automatically generate new reordering rules if not existed!",
                                          default=True)

    def accept_confirmation(self):
        """ Function override the action for button "YES"

        :return:
        """
        # get id of the selected records from the context
        record_ids = ast.literal_eval(self.env.context.get('record_ids'))
        if self.is_zero_max_qty(record_ids=record_ids):
            view_id = self.env.ref('reordering_rules_with_forecast.view_ignore_apply_zero_max_qty_form').id
            return {
                'type': 'ir.actions.act_window',
                'name': _('Confirmation'),
                'res_model': 'ignore.apply.zero.new.max.qty',
                'view_id': view_id,
                'view_mode': 'form',
                'view_type': 'form',
                'context': {
                    'message': 'All rules with the new max quantity equal to zero will be ignored.',
                    'auto_generate_new_rr': '1' if self.auto_generate_new_rr else '',
                    'record_ids': self.env.context.get('record_ids'),
                },
                'target': 'new',
            }
        else:
            self.env['reordering.rules.with.forecast']\
                .sudo()\
                .search([('id', 'in', record_ids)])\
                .generate_new_reordering_rules(auto_generate_new_rr=self.auto_generate_new_rr)

    def cancel_confirmation(self):
        """ Function override the action for button "NO"

        :return:
        """
        return {'type': 'ir.actions.act_window_close'}

    def is_zero_max_qty(self, record_ids):
        records = self.env['reordering.rules.with.forecast'].sudo().search([('id', 'in', record_ids)])
        for record in records:
            if record.new_max_qty == 0:
                return True
        return False
