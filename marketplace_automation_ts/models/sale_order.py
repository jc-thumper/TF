import logging
from odoo import models, fields, _

_logger = logging.getLogger("Teqstars: Marketplace Automation")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    order_workflow_id = fields.Many2one("order.workflow.config.ts", "Marketplace Workflow")

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        if self.order_workflow_id:
            if self.order_workflow_id.sale_journal_id:
                invoice_vals.update({'journal_id': self.order_workflow_id.sale_journal_id.id})
            if self.order_workflow_id.force_invoice_date:
                invoice_vals.update({'invoice_date': self.date_order})
        return invoice_vals

    def process_order(self, order_workflow_id):
        try:
            if self.state not in ['sale', 'done']:
                self.action_confirm()
            if self.env.context.get('create_date', False):
                self.write({'date_order': self.env.context.get('create_date')})
            if order_workflow_id.is_lock_order and self.state != 'done':
                self.action_done()
        except Exception as e:
            mk_log_id = self.env.context.get('mk_log_id', False)
            log_message = "PROCESS ORDER: Error while processing Marketplace Order {}, ERROR: {}".format(self.name, e)
            if mk_log_id:
                queue_line_id = self.env.context.get('queue_line_id', False)
                self.env['mk.log'].create_update_log(mk_log_id=mk_log_id,
                                                     mk_log_line_dict={'error': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
            _logger.error(_(log_message))
            return False
        return True

    def _prepare_payment_vals(self, order_workflow_id, invoice_id):
        journal_payment_method = order_workflow_id.journal_id.inbound_payment_method_ids
        payment_vals = {
            'invoice_ids': [(6, 0, invoice_id.ids)],
            'amount': invoice_id.amount_residual,
            'payment_date': invoice_id.date,
            'communication': invoice_id.invoice_payment_ref,
            'partner_id': invoice_id.commercial_partner_id.id,
            'partner_type': 'customer',
            'journal_id': order_workflow_id.journal_id.id,
            'payment_type': 'inbound',
            'payment_method_id': journal_payment_method and journal_payment_method[0].id or False,
        }
        return payment_vals

    def pay_and_reconcile(self, order_workflow_id, invoice_id):
        payment_vals = self._prepare_payment_vals(order_workflow_id, invoice_id)
        payment = self.env['account.payment'].create(payment_vals)
        payment.post()
        return True

    def process_invoice(self, order_workflow_id):
        try:
            if order_workflow_id.is_create_invoice:
                self._create_invoices()
            if order_workflow_id.is_validate_invoice:
                for invoice_id in self.invoice_ids:
                    invoice_id.action_post()
                    if order_workflow_id.is_register_payment:
                        self.pay_and_reconcile(order_workflow_id, invoice_id)
        except Exception as e:
            mk_log_id = self.env.context.get('mk_log_id', False)
            log_message = "PROCESS ORDER: Error while Create/Process Invoice for Marketplace Order {}, ERROR: {}".format(self.name, e)
            if mk_log_id:
                queue_line_id = self.env.context.get('queue_line_id', False)
                self.env['mk.log'].create_update_log(mk_log_id=mk_log_id,
                                                     mk_log_line_dict={'error': [{'log_message': log_message, 'queue_job_line_id': queue_line_id and queue_line_id.id or False}]})
            _logger.error(_(log_message))
            return False
        return True

    def do_marketplace_workflow_process(self, marketplace_workflow_id=False, order_list=None):
        if order_list is None or not order_list:
            order_list = [self]
        if not order_list:
            return False
        for order_id in order_list:
            order_workflow_id = order_id.order_workflow_id
            if not order_workflow_id:
                order_workflow_id = marketplace_workflow_id
            if order_id.invoice_status and order_id.invoice_status == 'invoiced':
                continue

            # Process Sale Order
            if order_workflow_id.is_confirm_order:
                if not order_id.process_order(order_workflow_id):
                    continue
                if order_workflow_id.invoice_policy == 'delivery':
                    continue

                # Process Invoice
                if not order_id.invoice_ids:
                    if not order_id.process_invoice(order_workflow_id):
                        continue
        return True
