# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp


class ResCompany(models.Model):
    _inherit = 'res.company'

    ###############################
    # FIELDS
    ###############################
    po_perc = fields.Float('Quantity We Order from PO', digits=dp.get_precision('Adjust Percentage'), default=20)
