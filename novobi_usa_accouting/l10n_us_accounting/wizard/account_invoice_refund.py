# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from ..models.account_mixin import AccountMixinUSA
from ..models.model_const import ACCOUNT_ACCOUNT
from ..utils import action_utils


class AccountInvoiceRefundUSA(models.TransientModel, AccountMixinUSA):
    """Write Off Bad Debt"""

    _name = 'account.invoice.refund.usa'
    _inherit = 'account.move.reversal'
    _description = 'Write Off An Account'

    def _default_write_off_amount(self):
        inv_obj = self.env['account.move']
        context = dict(self._context or {})
        for inv in inv_obj.browse(context.get('active_ids')):
            self._validate_state(inv.state)
            return inv.amount_residual
        return 0.0

    def _default_bad_debt_account_id(self):
        return self.env.user.company_id.bad_debt_account_id.id \
            if self.env.user.company_id.bad_debt_account_id else False

    write_off_amount = fields.Monetary(string='Write Off Amount', default=_default_write_off_amount,
                                       currency_field='company_currency_id', required=True)
    company_currency_id = fields.Many2one('res.currency', readonly=True,
                                          default=lambda self: self.env.user.company_id.currency_id)
    account_id = fields.Many2one(ACCOUNT_ACCOUNT, string='Account', required=True, default=_default_bad_debt_account_id,
                                 domain=[('deprecated', '=', False)])
    company_id = fields.Many2one('res.company', string='Company', change_default=True, readonly=True,
                                 default=lambda self: self.env['res.company']._company_default_get('account.move'))

    @api.constrains('write_off_amount')
    def _check_write_off_amount(self):
        for record in self:
            if record.write_off_amount <= 0:
                raise ValidationError(_('Amount must be greater than 0.'))

    def action_write_off(self):
        inv_obj = self.env['account.move']
        context = dict(self._context or {})
        is_apply = self.env.context.get('create_and_apply', False)

        refund_list = []
        for form in self:
            for inv in inv_obj.browse(context.get('active_ids')):
                self._validate_state(inv.state)

                description = form.reason or inv.name
                refund = inv.create_refund(form.write_off_amount, form.company_currency_id, form.account_id,
                                           form.date, description, inv.journal_id.id)

                # Put the reason in the chatter
                subject = 'Write Off An Account'
                body = description
                refund.message_post(body=body, subject=subject)

                refund_list.append(refund)

                if is_apply:  # validate, reconcile and stay on invoice form.
                    to_reconcile_lines = inv.line_ids.filtered(lambda line:
                                                                       line.account_id.id == line.partner_id.property_account_receivable_id.id)
                    refund.action_post()  # validate write-off
                    to_reconcile_lines += refund.line_ids.filtered(lambda line:
                                                                           line.account_id.id == line.partner_id.property_account_receivable_id.id)
                    to_reconcile_lines.filtered(lambda l: l.reconciled == False).reconcile()
                    return True

        return self.redirect_to_edit_mode_form('l10n_us_accounting.write_off_form_usa', refund_list[0].id, self._module,
                                               'action_invoice_write_off_usa') if refund_list else True

    @staticmethod
    def _validate_state(state):
        if state in ['draft', 'cancel']:
            raise UserError('Cannot create write off an account for the draft/cancelled invoice.')
