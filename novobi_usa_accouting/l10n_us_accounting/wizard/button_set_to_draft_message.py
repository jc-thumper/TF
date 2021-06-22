from odoo import fields, models, api


class AccountPaymentToDraftPopup(models.TransientModel):
    _name = 'button.draft.message'
    _description = 'Confirmed message when setting Payment/JE to draft'

    payment_id = fields.Many2one('account.payment', string='Payment')
    move_id = fields.Many2one('account.move', string='Journal Entry')
    message = fields.Html('Confirmed message', sanitize_attributes=False)

    @api.model
    def default_get(self, fields):
        res = super(AccountPaymentToDraftPopup, self).default_get(fields)
        context = self.env.context

        if context.get('default_payment_id', False):
            payment_id = self.env['account.payment'].browse(context['default_payment_id'])
            res['message'] = self._get_confirmed_message_payment(payment_id)
        elif context.get('default_move_id', False):
            move_id = self.env['account.move'].browse(context['default_move_id'])
            res['message'] = self._get_confirmed_message_move(move_id)

        return res

    def _applied_message_payment(self, payment):
        """
        This function will be override in deposit module
        :param payment: record of model account.payment
        :return: message
        """
        message = False
        if payment.open_invoice_ids:
            if payment.payment_type == 'inbound':
                message = "This payment has been applied{}. Reset it to draft will remove it from all related invoice(s)"
            elif payment.payment_type == 'outbound':
                message = "This payment has been applied{}. Reset it to draft will remove it from all related bill(s)"

        return message

    def _get_confirmed_message_payment(self, payment):
        """
        Get confirmed message when clicking 'Reset to draft' on payment form.
        :param payment: record of model account.payment
        :return: message
        """
        message = False
        if payment and payment.state != 'draft':
            # Check if this payment has been applied for any invoice/bill or reconciled yet
            message = self._applied_message_payment(payment)

            if payment.state == 'reconciled':
                # If it has been both applied for invoice/bill and reconciled. Ex: match BSL - invoice/bill => payment
                if message:
                    message = message.format(" and reconciled") + " and make your reconciliation unbalanced."
                # If it has just been reconciled. Ex: match BSL - payment.
                else:
                    message = "This payment has been reconciled. Reset it to draft will affect your reconciliation data."
            elif payment.has_been_reviewed:
                # If it has been both applied for invoice/bill and reviewed. Ex: match BSL - invoice/bill => payment
                if message:
                    message = message.format(" and matched with a bank statement line") + "."
                # If it has just been reviewed. Ex: match BSL - payment.
                else:
                    message = "This payment has been matched with a bank statement line."
            elif message:
                message = message.format("") + "."

            if message:
                message += "<br/>Do you still want to continue?"
            else:
                # If this payment has been neither applied to any invoice/bill nor reviewed/reconciled yet.
                message = "Are you sure you want to set this payment to draft?"
        return message

    def _get_confirmed_message_move(self, move):
        """
        Get confirmed message when clicking 'Reset to draft' on move (Invoice/Bill/.../JE) form.
        :param move: record of model account.move
        :return: message
        """
        message = False
        if move and move.state != 'draft':
            if move.type != 'entry' and move.invoice_payments_widget != 'false':
                message = "Reset to draft will unlink all payments which have been paid for this transaction."
            elif move.line_ids.filtered('bank_reconciled'):
                message = "This transaction has been reconciled. Reset it to draft will affect your reconciliation data."
            elif move.type == 'entry' and move.has_been_reviewed:
                message = "This transaction has been reviewed for bank reconciliation. Reset it to draft will affect your reconciliation data."

            if message:
                message += "<br/>Do you still want to continue?"
            else:
                message = "Are you sure you want to set this transaction to draft?"
        return message

    def button_set_to_draft(self):
        self.ensure_one()
        if self.payment_id:
            self.payment_id.action_draft()
        elif self.move_id:
            self.move_id.button_draft()
