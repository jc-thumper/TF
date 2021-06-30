from odoo import models, fields, api
from odoo.tools.translate import _


class AccountMoveReversal(models.TransientModel):
    """
    Account move reversal wizard, it cancel an account move by reversing it.
    """
    _inherit = 'account.move.reversal'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self._context.get('active_model', False) == 'account.payment':
            res['refund_method'] = 'cancel'
        return res

    def reverse_moves(self):
        if self._context.get('active_model', False) == 'account.payment':
            payment_id = self._context.get('active_id', False)

            if payment_id:
                payment = self.env['account.payment'].browse(payment_id)
                ac_move_ids = payment.move_line_ids.mapped('move_id')

                # Create default values.
                default_values_list = []
                for move in ac_move_ids:
                    default_values_list.append(self._prepare_default_reversal(move))

                # refund_method = cancel, and auto post
                new_moves = ac_move_ids.with_context(from_payment=payment_id)._reverse_moves(default_values_list, cancel=True)

                if new_moves:
                    payment.has_been_voided = True
                    msg = "This payment has been voided. The reverse entries were created: {}".format(', '.join([record.name for record in new_moves]))
                    payment.message_post(body=msg, message_type="comment", subtype="mail.mt_note")

                    return {
                        'name': _('Reverse Moves'),
                        'type': 'ir.actions.act_window',
                        'view_type': 'form',
                        'view_mode': 'tree,form',
                        'res_model': 'account.move',
                        'domain': [('id', 'in', new_moves.ids)],
                    }
            return {'type': 'ir.actions.act_window_close'}
        else:
            return super().reverse_moves()
