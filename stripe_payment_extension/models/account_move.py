# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def create_and_open_payment(self):
        self.ensure_one()
        payment_link_wiz = self.env['payment.link.wizard'].create({
            'res_model': "account.move",
            'res_id': self.id,
            'amount': self.amount_residual,
            'amount_max': self.amount_residual,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'description': self.invoice_payment_ref,
        })

        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': payment_link_wiz.link,
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
