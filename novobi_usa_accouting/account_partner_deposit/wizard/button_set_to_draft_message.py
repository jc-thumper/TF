from odoo import fields, models, api


class AccountPaymentToDraftPopup(models.TransientModel):
    _inherit = 'button.draft.message'

    def _applied_message_payment(self, payment):
        """
        This function will be override in deposit module
        :param payment: record of model account.payment
        :return: message
        """
        if not payment.is_deposit:
            return super()._applied_message_payment(payment)

        message = False
        if payment.deposit_ids:
            if payment.payment_type == 'inbound':
                message = "This payment has been applied{}. Reset it to draft will remove it from all related invoice(s)"
            elif payment.payment_type == 'outbound':
                message = "This payment has been applied{}. Reset it to draft will remove it from all related bill(s)"

        return message
