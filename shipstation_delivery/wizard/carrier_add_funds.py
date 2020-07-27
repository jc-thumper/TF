# -*- coding: utf-8 -*-

from odoo import api, fields, models


class CarrierAddFunds(models.TransientModel):
    _name = "carrier.add.funds"
    _description = "Carrier Add Funds"

    amount = fields.Float("Amount", required=True)

    @api.model
    def default_get(self, fields):
        res = super(CarrierAddFunds, self).default_get(fields)
        return res

    def process_add_funds(self):
        active_ids = self.env.context.get('active_ids', [])
        carriers = self.env['shipstation.carrier'].browse(active_ids)
        for carrier in carriers:
            prepared_vals = {"carrierCode": carrier.code, "amount": self.amount}
            carrier.account_id._send_request('carriers/addfunds', prepared_vals, method="POST")
        return True
