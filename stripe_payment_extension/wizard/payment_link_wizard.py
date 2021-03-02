# -*- encoding: utf-8 -*-

from odoo import api, fields, models
from werkzeug import urls


class PaymentLinkWizard(models.TransientModel):
    _inherit = "payment.link.wizard"

    def _generate_link(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for payment_link in self:
            res_id = self.res_id
            res_model = self.res_model
            reference = urls.url_quote(payment_link.description)
            if res_id and res_model == 'account.move':
                record = self.env[res_model].browse(res_id)
                reference = urls.url_quote(record.name)
            link = ('%s/website_payment/pay?reference=%s&amount=%s&currency_id=%s'
                    '&partner_id=%s&access_token=%s') % (
                       base_url,
                       reference,
                       payment_link.amount,
                       payment_link.currency_id.id,
                       payment_link.partner_id.id,
                       payment_link.access_token
                   )
            if payment_link.company_id:
                link += '&company_id=%s' % payment_link.company_id.id
            payment_link.link = link


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
