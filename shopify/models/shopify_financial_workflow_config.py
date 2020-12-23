from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

FINANCIAL_STATUS = [('authorized', 'Order financial is authorized'),
                    ('pending', 'Order financial is pending'),
                    ('paid', 'Order financial is paid'),
                    ('partially_paid', 'Order financial is partially paid'),
                    ('refunded', 'Order financial is refunded'),
                    ('voided', 'Order financial is voided'),
                    ('partially_refunded', 'Order financial is partially refunded'),
                    ('any', 'Order financial is any'),
                    ('unpaid', 'Order financial is unpaid')]


class ShopifyFinancialWorkflowConfig(models.Model):
    _name = 'shopify.financial.workflow.config'
    _description = "Shopify Financial Workflow Configuration"

    mk_instance_id = fields.Many2one('mk.instance', "Instance", ondelete='cascade')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')
    order_workflow_id = fields.Many2one("order.workflow.config.ts", "Marketplace Workflow")
    payment_gateway_id = fields.Many2one("shopify.payment.gateway.ts", "Payment Gateway")
    financial_status = fields.Selection(FINANCIAL_STATUS, help="Shopify Order's Financial Status.")

    # _sql_constraints = [
    #     ('financial_workflow_unique_constraint', 'unique(mk_instance_id,payment_gateway_id,financial_status)', "You cannot create duplicate Financial Workflow Configuration.")]

    @api.constrains('mk_instance_id', 'payment_gateway_id', 'financial_status')
    def _check_unique_financial_workflow(self):
        for workflow in self:
            domain = [('id', '!=', workflow.id), ('mk_instance_id', '=', workflow.mk_instance_id.id), ('payment_gateway_id', '=', workflow.payment_gateway_id.id),
                      ('financial_status', '=', workflow.financial_status)]
            if self.search(domain):
                raise ValidationError(_('You cannot create duplicate Financial Workflow Configuration!'))
