from odoo import api, fields, models, _


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    is_changed_bom = fields.Boolean(string="BOM Change")
