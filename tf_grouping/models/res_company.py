from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    allow_grouping_bom = fields.Boolean(string='Allow group RFQs by BOM')
    vendor_ids = fields.Many2many('res.partner', string='Vendors', help='List of vendors who can group RFQs by BOM')
