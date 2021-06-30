# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, format_date


class AccountFollowupDepositReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_lines(self, options, line_id=None):
        lines = super(AccountFollowupDepositReport, self)._get_lines(options, line_id)

        partner = options.get('partner_id') and self.env['res.partner'].browse(options['partner_id']) or False
        if not partner:
            return []
        lang_code = partner.lang or self.env.user.lang or 'en_US'

        res = {}
        for l in partner.customer_deposit_aml_ids:
            if l.company_id == self.env.user.company_id:
                if self.env.context.get('print_mode') and l.blocked:
                    continue
                currency = l.currency_id or l.company_id.currency_id
                if currency not in res:
                    res[currency] = []
                res[currency].append(l)

        for currency, aml_recs in res.items():
            total = 0
            for line in aml_recs:
                if self.env.context.get('print_mode') and line.blocked:
                    continue

                amount = line.currency_id and line.amount_residual_currency or line.amount_residual
                total += not line.blocked and amount or 0
                amount = formatLang(self.env, amount, currency_obj=currency)
                columns = [format_date(self.env, line.date, lang_code=lang_code),
                           {'name': line.move_id.ref, 'class': ' number'},
                           {'name': line.blocked, 'blocked': line.blocked}, amount]

                if self.env.context.get('print_mode'):
                    columns = columns[:2] + columns[3:]

                lines.append({
                    'id': line.id,
                    'view_invoice_id': self.env['ir.model.data'].get_object_reference('account', 'view_move_form')[1],
                    'account_move': line.move_id,
                    'deposit_line': True,
                    'name': line.move_id.name,
                    'caret_options': 'followup',
                    'move_id': line.move_id.id,
                    'unfoldable': False,
                    'has_invoice': bool(line.move_id),
                    'columns': [type(v) == dict and v or {'name': v} for v in columns],
                })

            total_due = formatLang(self.env, total, currency_obj=currency)
            lines.append({
                'id': 1,
                'name': '',
                'deposit_line': True,
                'class': 'total',
                'style': 'border-top-style: double',
                'unfoldable': False,
                'level': 3,
                'columns': [{'name': v} for v in [''] * (1 if self.env.context.get('print_mode') else 2) + [
                    partner.total_due >= 0 and _('Total Deposit') or '', total_due]],
            })

        return lines
