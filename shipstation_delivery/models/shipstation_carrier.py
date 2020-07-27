# -*- coding: utf-8 -*-
import time
import json
import pytz
import base64
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, Warning


class ShipstationCarrier(models.Model):
    _name = "shipstation.carrier"
    _description = "Shipstation Carrier"

    name = fields.Char("Name", required=True, help="This is how the Carrier will be named in ShipStation.")
    code = fields.Char("Code", required=True)
    primary = fields.Boolean("Primary")
    account_number = fields.Char("Account Number")
    requires_funded_account = fields.Boolean("Requires Funded Account")
    balance = fields.Float("Balance")
    nick_name = fields.Char("Nick Name")
    shipping_provide_id = fields.Char("Shipping Provider ID")
    account_id = fields.Many2one("shipstation.accounts", "Accounts", required=True, ondelete='restrict',
                                 help="Account in which carrier is configured")

    def open_service_view(self):
        [action] = self.env.ref('shipstation_delivery.action_shipstation_service').read()
        action['domain'] = [('carrier_id.code', '=', self.code)]
        return action

    def open_package_view(self):
        [action] = self.env.ref('shipstation_delivery.action_shipstation_packages').read()
        action['domain'] = [('carrier_id', '=', self.id)]
        return action

    def import_carrier(self, account=False):
        if not account:
            raise Warning("Shipstation Account not defined to import Carrier list")
        response = account._send_request('carriers', {})
        for carrier in response:
            shipping_provide_id = carrier.get('shippingProviderId')
            prepared_vals = {
                "name": carrier.get('name'),
                "code": carrier.get('code'),
                "primary": carrier.get('primary'),
                "account_number": carrier.get("accountNumber"),
                "requires_funded_account": carrier.get("requiresFundedAccount"),
                "balance": carrier.get('balance'),
                "nick_name": carrier.get('nickname'),
                "shipping_provide_id": shipping_provide_id,
                "account_id": account.id,
            }
            existing_carrier = self.search([('shipping_provide_id', '=', shipping_provide_id)], limit=1)
            if existing_carrier:
                existing_carrier.write(prepared_vals)
            else:
                carrier = self.create(prepared_vals)
                carrier.import_packages()
        return True

    def import_packages(self):
        self.ensure_one()
        shipstation_package_obj = self.env['shipstation.packages']
        if not self.account_id:
            raise Warning("Shipstation Account not defined to import package list")
        response = self.account_id._send_request('carriers/listpackages?carrierCode=%s' %self.code, {})
        for package in response:
            package_exist = shipstation_package_obj.search(
                [('account_id', '=', self.account_id.id), ('carrier_id', '=', self.id),
                 ('code', '=', package.get('code'))])
            if package_exist:
                continue
            shipstation_package_obj.create({
                'name': package.get('name', False),
                'code': package.get('code', False),
                'is_domestic': package.get('domestic', False),
                'is_international': package.get('international', False),
                'carrier_id': self.id,
                'account_id': self.account_id.id
            })
        return True

    def refresh_carrier(self):
        if not self.account_id:
            raise Warning("Shipstation Account not defined to import Carrier list")
        response = self.account_id._send_request('carriers/getcarrier?carrierCode=%s' % self.code, {})
        prepared_vals = {
            "name": response.get('name'),
            "code": response.get('code'),
            "primary": response.get('primary'),
            "account_number": response.get("accountNumber"),
            "requires_funded_account": response.get("requiresFundedAccount"),
            "balance": response.get('balance'),
            "nick_name": response.get('nickname'),
            "shipping_provide_id": response.get('shippingProviderId'),
        }
        self.write(prepared_vals)
        return True
