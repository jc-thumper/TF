# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, Warning

class ShipstationMarketplaces(models.Model):
    _name = "shipstation.marketplace"
    _description = "Shipstation Marketplaces"
    
    name = fields.Char("Name", required=True, readonly=True)
    marketplace_id = fields.Integer("Marketplace ID")
    can_refresh = fields.Boolean("Can Refresh")
    supports_custom_mappings = fields.Boolean("Supports Custom Mappings")
    supports_custom_statues = fields.Boolean("Supports Custom Statues")
    can_confirm_shipments = fields.Boolean("Can Confirm Shipments")

    def import_marketplaces(self, account=False):
        if not account :
            raise Warning("Shipstation Account not defined to import Marketplaces")
        response = account._send_request('stores/marketplaces', {}, method='GET')
        for marketplace in response :
            marketplace_id = marketplace.get('marketplaceId')
            existing_marketplace = self.search([('marketplace_id','=', marketplace_id)])
            if existing_marketplace :
                continue
            prepared_vals = {
                "name" : marketplace.get('name'),
                "marketplace_id" : marketplace.get('marketplaceId'),
                "can_refresh" : marketplace.get('canRefresh'),
                "supports_custom_mappings" : marketplace.get('supportsCustomMappings'),
                "supports_custom_statues" : marketplace.get('supportsCustomStatuses'),
                "can_confirm_shipments" : marketplace.get('canConfirmShipments')
            }
            self.create(prepared_vals)
        return True     