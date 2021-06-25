# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    ###############################
    # FIELDS
    ###############################
    forecast_config_ids = fields.One2many('product.forecast.config', 'product_id')

