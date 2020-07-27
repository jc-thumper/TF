# -*- coding: utf-8 -*-
import pytz
from datetime import datetime
from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError, Warning


class ShipstationStore(models.Model):
    _name = "shipstation.store"
    _description = "Shipstation Store"

    name = fields.Char("Name", required=True, help="This is how the Store will be named in ShipStation.")
    store_id = fields.Integer('Store ID')
    marketplace_id = fields.Many2one('shipstation.marketplace', 'Marketplace', ondelete='restrict')
    account_id = fields.Many2one("shipstation.accounts", "Accounts", required=True, ondelete='restrict',
                                 help="Account in which store is configured")
    email = fields.Char('Email')
    integration_url = fields.Char('Integration URL')
    active = fields.Boolean('Is Active?', help="Inactive stores are hidden throughout ShipStation")
    company_name = fields.Char('Company Name')
    phone = fields.Char('Phone')
    public_email = fields.Char("Public Email")
    website = fields.Char('Website')
    auto_refresh = fields.Boolean("Allow this store to 'auto-update' periodically?",
                                  help="Allow this store to 'auto-update' periodically?")
    last_refresh_attempt = fields.Datetime("Last Refresh Attempt", help="Last refresh attempt for store")

    # Order Statuses
    support_custom_statues = fields.Boolean(related="marketplace_id.supports_custom_statues")
    awaiting_payment = fields.Char("Awaiting Payment Statuses",
                                   help="Orders that are in this status cannot be shipped. They must be marked as paid, which moves them to Awaiting Shipment. Keep in mind that some marketplaces do not import unpaid orders into Awaiting Payment.")
    awaiting_shipment = fields.Char("Awaiting Shipment Statuses",
                                    help="This status displays all open orders that need to be shipped. Enter any order status that you use that states an order is ready for shipping.")
    shipped = fields.Char("Shipped Statuses",
                          help="Orders in this status were either shipped using ShipStation (that is, they had a label created or were marked as shipped by a user in ShipStation), were imported as shipped from the marketplace (because they were shipped outside of ShipStation and the status updated before the order imported), or updated by a marketplace refresh (again, shipped outside of ShipStation and marked as shipped on your marketplace). ")
    cancelled = fields.Char("Cancelled Statuses",
                            help="Orders in this status have either been updated as cancelled by the marketplace or cancelled within ShipStation. Please note that ShipStation updates orders as cancelled from your marketplace; however, if you cancel an order in ShipStation, it will not update back to your marketplace.")
    on_hold = fields.Char("On-Hold Statuses",
                          help="Displays orders that have been manually placed 'On Hold', because the item is on back-order, is partially fulfilled, etc. Orders can be taken out of on hold via the 'Hold Until' date expiration, manual order status adjustment in ShipStation, or marketplace status update.")

    def import_stores(self, account=False):
        if not account:
            raise Warning("Shipstation Account not defined to import Stores")
        response = account._send_request('stores?showInactive=True', {}, method='GET')
        for store in response:
            store_id = store.get('storeId')
            marketplace_id = self.env['shipstation.marketplace'].search(
                [('marketplace_id', '=', store.get('marketplaceId'))])
            prepared_vals = {
                "name": store.get('storeName'),
                "store_id": store_id,
                "marketplace_id": marketplace_id.id,
                "account_id": account.id,
                "email": store.get('email'),
                "integration_url": store.get('integrationUrl'),
                "active": store.get('active'),
                "company_name": store.get('companyName'),
                "phone": store.get('phone'),
                "public_email": store.get('publicEmail'),
                "website": store.get('website'),
                "auto_refresh": store.get('autoRefresh'),
            }
            if store.get('statusMappings') is not None:
                for status in store.get('statusMappings', []):
                    status_field = status.get("orderStatus")
                    status_field_value = status.get("statusKey")
                    prepared_vals.update({status_field: status_field_value})
            existing_store = self.search([('store_id', '=', store_id)], limit=1)
            if existing_store:
                existing_store.write(prepared_vals)
            else:
                self.create(prepared_vals)
        return True

    def update_store_info(self):
        for store in self:
            prepared_vals = {
                "storeId": store.store_id,
                "storeName": store.name,
                "marketplaceId": store.marketplace_id.id,
                "marketplaceName": store.marketplace_id.name,
                "email": store.email or None,
                "integrationUrl": store.integration_url or None,
                "active": store.active,
                "companyName": store.company_name or None,
                "phone": store.phone or None,
                "publicEmail": store.public_email or None,
                "website": store.website or None,
                "autoRefresh": store.auto_refresh,
            }
            if store.support_custom_statues:
                prepared_vals.update({
                    "statusMappings": [
                        {
                            "orderStatus": "awaiting_payment",
                            "statusKey": store.awaiting_payment or ''
                        },
                        {
                            "orderStatus": "awaiting_shipment",
                            "statusKey": store.awaiting_shipment or ''
                        },
                        {
                            "orderStatus": "shipped",
                            "statusKey": store.shipped or ''
                        },
                        {
                            "orderStatus": "cancelled",
                            "statusKey": store.cancelled or ''
                        },
                        {
                            "orderStatus": "on_hold",
                            "statusKey": store.on_hold or ''
                        }]})
            response = store.account_id._send_request('stores/%s' % store.store_id, prepared_vals, method='PUT')
        return True

    def reactive_store(self):
        if not self.active and self.store_id:
            prepared_vals = {'storeId': self.store_id}
            response = self.account_id._send_request('stores/reactivate', prepared_vals, method='POST')
            if response.get('success'):
                self.active = True
            else:
                raise Warning("The requested store has not been reactivated.")
        return True

    def deactive_store(self):
        if self.active and self.store_id:
            prepared_vals = {'storeId': self.store_id}
            response = self.account_id._send_request('stores/deactivate', prepared_vals, method='POST')
            if response.get('success'):
                self.active = False
            else:
                raise Warning("The requested store has not been deactivated.")
        return True

    def refresh_store(self):
        for store in self :
            if store.active and store.store_id :
                prepared_vals = {'storeId': self.store_id}
                response = store.account_id._send_request('stores/refreshstore?storeId=%s' % self.store_id, prepared_vals, method='POST')
                store.get_store_refresh_status()
        return True

    def get_store_refresh_status(self):
        if self.active and self.store_id :
            prepared_vals = {'storeId': self.store_id}
            response = self.account_id._send_request('stores/getrefreshstatus?storeId=%s' % self.store_id, prepared_vals)
            last_attempt = response.get('lastRefreshAttempt',False)
            if last_attempt:
                self.last_refresh_attempt = self.account_id.covert_date(last_attempt)
        return True