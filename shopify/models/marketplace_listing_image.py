from odoo import models, fields
import logging

_logger = logging.getLogger("Teqstars:Shopify")


class ListingImage(models.Model):
    _inherit = 'mk.listing.image'

    shopify_alt_text = fields.Char("alt text")
