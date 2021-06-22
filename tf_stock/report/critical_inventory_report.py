from odoo import api, fields, models, _


class CriticalReport(models.Model):
    _inherit = 'product.product'

    critical_threshold = fields.Float(string='Critical Threshold', digits='Product Unit of Measure')
    is_qoh_critical = fields.Boolean(string='Check forecast quantity and safety stock target',
                                     compute='_compute_qoh_critical', search='_search_qoh_critical')

    @api.depends('qty_available', 'critical_threshold')
    def _compute_qoh_critical(self):
        for record in self:
            record.is_qoh_critical = False
            if record.critical_threshold > 0 and record.qty_available < record.critical_threshold:
                record.is_qoh_critical = True

    def _search_qoh_critical(self, operator, value):
        product_ids = []
        if operator == '=' and value:
            product_ids = self.env['product.product'].search([('critical_threshold', '>', 0)]).filtered(lambda p: p.qty_available < p.critical_threshold).ids
        return [('id', 'in', product_ids)]

    def button_view_rfq(self):
        self.ensure_one()
        inprogress_order_lines = self.env['purchase.order.line'].search(
            [('product_id', '=', self.id), ('state', 'not in', ['done', 'cancel'])])
        purchase_orders = inprogress_order_lines.filtered(lambda line: line.qty_received < line.product_qty).mapped('order_id')
        action = {
            'domain': [('id', 'in', purchase_orders.ids)],
            'name': 'Requests for Quotation',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
        }
        return action
