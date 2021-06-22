from odoo import api, fields, models, _


class Orderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    safety_stock_target = fields.Float(string='Safety Stock Target')
