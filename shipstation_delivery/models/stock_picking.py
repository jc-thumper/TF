from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    shipstation_shipment_id = fields.Char("ShipStation Shipment ID")
