from odoo import fields, api, models


class PrepareOrder(models.TransientModel):
    _name = "prepare.order"

    account_id = fields.Many2one('shipstation.accounts', string="Account", required=True)
    store_id = fields.Many2one('shipstation.store', string="Store", required=True)

    def do_prepare(self):
        active_ids = self._context.get('active_ids', []) or []
        orders = self.env['sale.order'].browse(active_ids)
        orders = orders.filtered(lambda x: x.state in ['sent', 'sale'])
        if not orders:
            return True
        orders.write({'shipstation_account_id': self.account_id.id, 'shipstation_store_id': self.store_id.id,
                      'prepared_for_shipstation': True})
        return True
        # orders.mapped('picking_ids').filtered(lambda x: x.state == 'assigned').write({'shipstation_account_id': self.account_id.id, 'shipstation_store_id': self.store_id.id})
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'reload',
        # }
