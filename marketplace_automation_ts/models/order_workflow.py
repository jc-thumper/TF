from odoo import models, fields, api


class OrderWorkflowConfig(models.Model):
    _name = "order.workflow.config.ts"
    _description = "Order Workflow Configuration"

    def _get_default_journal(self):
        if self.env.context.get('default_journal_type'):
            return self.env['account.journal'].search([('company_id', '=', self.env.user.company_id.id),
                                                       ('type', '=', self.env.context['default_journal_type'])],
                                                      limit=1).id

    name = fields.Char("Name", required=True, translate=True)

    is_confirm_order = fields.Boolean("Confirm Order", default=False)
    is_lock_order = fields.Boolean("Lock Confirmed Order", default=False, help="No longer edit orders once confirmed")

    is_create_invoice = fields.Boolean('Create Invoice', default=False)
    is_validate_invoice = fields.Boolean(string='Validate Invoice', default=False)
    is_register_payment = fields.Boolean(string='Register Payment', default=False)
    invoice_policy = fields.Selection([('order', 'Ordered quantities'), ('delivery', 'Delivered quantities')],
                                      string='Invoicing Policy',
                                      help='Ordered Quantity: Invoice quantities ordered by the customer.\n'
                                           'Delivered Quantity: Invoice quantities delivered to the customer.',
                                      default='order')

    journal_id = fields.Many2one('account.journal', string='Payment Journal', domain=[('type', 'in', ('bank', 'cash'))])
    sale_journal_id = fields.Many2one('account.journal', string='Order Journal', default=_get_default_journal)
    force_invoice_date = fields.Boolean(string='Force Invoice Date', default=False, help="Set Invoice date and Payment date same as Order date.")

    picking_policy = fields.Selection([
        ('direct', 'Deliver each product when available'),
        ('one', 'Deliver all products at once')], string='Shipping Policy', default='direct',
        help="If you deliver all products at once, the delivery order will be scheduled based on the greatest "
             "product lead time. Otherwise, it will be based on the shortest.")
