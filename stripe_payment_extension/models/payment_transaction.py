# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _prepare_account_payment_vals(self):
        vals = super(PaymentTransaction, self)._prepare_account_payment_vals()

        if self.provider == 'stripe' and self.reference:
            invoice_ref = self.reference[:13]
            invoice = self.env['account.move'].search([('name', '=', invoice_ref), ('company_id', '=', vals.get('company_id', 0))], limit=1)
            if invoice:
                vals['partner_id'] = invoice.partner_id.id
                if invoice.invoice_payment_state == 'not_paid' and not self.invoice_ids:
                    vals['invoice_ids'] = [(6, 0, invoice.ids)]
                vals['communication'] = invoice.invoice_payment_ref
        return vals


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
