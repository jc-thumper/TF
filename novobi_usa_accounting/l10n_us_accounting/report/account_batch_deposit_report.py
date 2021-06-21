# -*- coding: utf-8 -*-
from odoo import api, models

PAY_LINES_PER_PAGE = 20


class PrintBatchPayment(models.AbstractModel):
    _inherit = 'report.account_batch_payment.print_batch_payment'

    def get_pages(self, batch):
        """ Returns the data structure used by the template
        """
        transaction = [{'partner': payment.partner_id.name if payment.partner_id else False,
                        'date': payment.payment_date,
                        'communication': payment.communication,
                        'amount': payment.amount} for payment in batch.payment_ids]

        transaction.extend([{'partner': payment.partner_id.name if payment.partner_id else False,
                             'date': payment.payment_date,
                             'communication': payment.communication,
                             'amount': payment.amount} for payment in batch.fund_line_ids])
        i = 0
        payment_slices = []
        while i < len(transaction):
            payment_slices.append(transaction[i:i + PAY_LINES_PER_PAGE])
            i += PAY_LINES_PER_PAGE

        return [{
            'date': batch.date,
            'batch_name': batch.name,
            'journal_name': batch.journal_id.name,
            'payments': payments,
            'currency': batch.currency_id,
            'total_amount': batch.amount,
            'footer': batch.journal_id.company_id.report_footer,
        } for payments in payment_slices]
