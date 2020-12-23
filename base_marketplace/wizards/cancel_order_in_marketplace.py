from odoo import models, fields, api, _


class MKCancelOrder(models.TransientModel):
    _name = "mk.cancel.order"
    _description = "Cancel Order In Marketplace"

    is_create_refund = fields.Boolean("Create Refund?", default=False, help="Weather to Create Refund/Credit Note in Odoo?")
    refund_description = fields.Char("Refund Reason")
    date_invoice = fields.Date(string='Credit Note Date', default=fields.Date.context_today, required=True)
    payment_journal_id = fields.Many2one('account.journal', string='Payment Journal', domain=[('type', 'in', ('bank', 'cash'))])
    currency_id = fields.Many2one('res.currency', string='Currency')
    create_refund_option_visible = fields.Boolean("Allow Credit Note Creation", help="Technical field to identify user can create credit note or not.")

    @api.model
    def default_get(self, fields):
        res_id = self._context.get('active_id')
        order_id = self.env['sale.order'].browse(res_id)
        result = super(MKCancelOrder, self).default_get(fields)
        if not result.get('currency_id') and order_id:
            result.update({'currency_id': order_id.currency_id.id,
                           'create_refund_option_visible': True if order_id.invoice_ids.filtered(lambda x: x.type == 'out_invoice' and x.invoice_payment_state == 'paid') else False})
        return result
