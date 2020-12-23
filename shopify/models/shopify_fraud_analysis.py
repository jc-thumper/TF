from .. import shopify
from odoo import models, fields, _

RECOMMENDATION = [('cancel', 'Cancel'), ('investigate', 'Investigate'), ('accept', 'Accept')]


class ShopifyFraudAnalysis(models.Model):
    _name = "shopify.fraud.analysis"
    _description = "Fraud Analysis"

    name = fields.Char("Name", size=255, required=True)
    shopify_fraud_id = fields.Char("Fraud ID", copy=False)
    order_id = fields.Many2one("sale.order", string="Order", copy=False, ondelete="cascade")
    cause_cancel = fields.Boolean("Cause Cancel", copy=False, default=False,
                                  help="Whether this order risk is severe enough to force the cancellation of the order. If true, then this order risk is included in the Order "
                                       "canceled message that's shown on the details page of the canceled order.")
    display = fields.Boolean("Display Order Risk?", copy=False, default=True,
                             help="Whether the order risk is displayed on the order details page in the Shopify admin. If false, then this order risk is ignored when Shopify "
                                  "determines your app's overall risk level for the order.")
    message = fields.Char("Message", copy=False,
                          help="The message that's displayed to the merchant to indicate the results of the fraud check. The message is displayed only if display is set to true.")
    recommendation = fields.Selection(RECOMMENDATION, copy=False, default='cancel', help="The recommended action given to the merchant.")
    score = fields.Float("Score", default=1.0, copy=False,
                         help="For internal use only. A number between 0 and 1 that's assigned to the order. The closer the score is to 1, the more likely it is that the order "
                              "is fraudulent.")
    risk_source = fields.Char("Risk Source", copy=False, help="The source of the order risk.")

    def create_fraud_analysis(self, shopify_order_id, odoo_order_id):
        order_risks = shopify.OrderRisk().find(order_id=shopify_order_id)
        if order_risks:
            for order_risk in order_risks:
                order_risk_dict = order_risk.to_dict()
                risk_vals = {'name': order_risk_dict.get('order_id'),
                             'shopify_fraud_id': order_risk_dict.get('id'),
                             'cause_cancel': order_risk_dict.get('cause_cancel'),
                             'display': order_risk_dict.get('display'),
                             'message': order_risk_dict.get('message'),
                             'recommendation': order_risk_dict.get('recommendation'),
                             'score': order_risk_dict.get('score'),
                             'risk_source': order_risk_dict.get('source'),
                             'order_id': odoo_order_id.id}
                self.create(risk_vals)
            return True
        return False
