# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import date


class PrintPreNumberedChecks(models.TransientModel):
    _inherit = 'print.prenumbered.checks'

    def print_checks(self):
        if self.env.context.get('duplicate_confirm', False):
            return super(PrintPreNumberedChecks, self).print_checks()

        check_number = int(self.next_check_number)
        max_number = check_number + len(self.env.context['payment_ids'])
        payments = self.env['account.payment'].browse(self.env.context['payment_ids'])
        first_date = date.today().replace(month=1, day=1)
        last_date = date.today().replace(month=12, day=31)

        duplicate_check = self.env['account.payment'].search([
            ('journal_id', '=', payments[0].journal_id.id),
            ('payment_date', '>=', first_date), ('payment_date', '<=', last_date),
            ('check_number', '>=', check_number), ('check_number', '<', max_number)], limit=1)
        if duplicate_check:
            view_id = self.env.ref('l10n_us_accounting.print_pre_numbered_checks_warning_view').id
            return {
                'name': _('Confirmation'),
                'type': 'ir.actions.act_window',
                'res_model': 'print.prenumbered.checks',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'view_id': view_id,
                'res_id': self.id,
                'context': {
                    'duplicate_confirm': True,
                }
            }
        else:
            return super(PrintPreNumberedChecks, self).print_checks()

