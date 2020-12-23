from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    mk_instance_id = fields.Many2one('mk.instance', "Instance", copy=False)
    is_refunded_in_mk = fields.Boolean("Refunded in Marketplace", default=False, copy=False)

    # @api.model
    # def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
    #     values = super(AccountMove, self)._prepare_refund(invoice, date_invoice=date_invoice, date=date, description=description, journal_id=journal_id)
    #     values.update({'mk_instance_id': invoice.mk_instance_id.id})
    #     return values

    def _reverse_moves(self, default_values_list=None, cancel=False):
        # TODO: Test Remaining
        if not default_values_list:
            default_values_list = [{} for move in self]
        for move, default_values in zip(self, default_values_list):
            default_values.update({
                'mk_instance_id': move.mk_instance_id.id,
            })
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)
