from odoo import fields, models, _


class StockInventory(models.Model):
    _inherit = "stock.inventory"

    is_marketplace_adjustment = fields.Boolean("Is Marketplace Adjustment")


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_new_picking_values(self):
        res = super(StockMove, self)._get_new_picking_values()
        order_id = self.sale_line_id.order_id
        if order_id.mk_id:
            res.update({'mk_instance_id': order_id.mk_instance_id.id})
            if order_id.updated_in_marketplace:
                res.update({'updated_in_marketplace': True})
        return res

    def _assign_picking_post_process(self, new=False):
        super(StockMove, self)._assign_picking_post_process(new=new)
        if new and self.env.context.get('create_date', False):
            order_id = self.sale_line_id.order_id
            if order_id.mk_id:
                picking_id = self.mapped('picking_id')
                picking_id.scheduled_date = self.env.context.get('create_date')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    updated_in_marketplace = fields.Boolean("Updated in Marketplace?", default=False, copy=False)
    cancel_in_marketplace = fields.Boolean("Cancel in Marketplace", default=False, copy=False)
    mk_instance_id = fields.Many2one('mk.instance', "Marketplace Instance", ondelete='cascade', copy=False)
