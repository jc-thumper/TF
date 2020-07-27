from odoo import models, fields, api


class ShipstationPackages(models.Model):
    _name = 'shipstation.packages'
    _description = 'Shipstation Packages'

    name = fields.Char(string='Name')
    code = fields.Char(string='Code')
    is_domestic = fields.Boolean(string='Is Domestic?')
    is_international = fields.Boolean(string='Is International?')
    carrier_id = fields.Many2one('shipstation.carrier', string='Shipstation Carrier', ondelete='cascade')
    account_id = fields.Many2one('shipstation.accounts', string='Account')

    is_your_packaging = fields.Boolean(string='Your Packaging')
    packaging_id = fields.Many2one('product.packaging', string="Package")
    # package_unit = fields.Selection([('inches', 'Inches'), ('centimeters', 'Centimeters')], string="Package Unit")
    # height = fields.Float(string="Height")
    # width = fields.Float(string="Width")
    # length = fields.Float(string="Length")
    # weight = fields.Float(string="Package Weight")
