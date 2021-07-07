from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allow_grouping_bom = fields.Boolean(string='Allow group RFQs by BOM', related='company_id.allow_grouping_bom', readonly=False)
    vendor_ids = fields.Many2many('res.partner', string='Vendors', related='company_id.vendor_ids', readonly=False,
                                  help='List of vendors who can group RFQs by BOM')
