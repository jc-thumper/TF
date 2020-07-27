# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ImportExportOperation(models.TransientModel):
    _name = "import.export.operation"
    _description = "Import Export Operation"

    account_ids = fields.Many2many('shipstation.accounts', required=True,
                                   help="Select Account from which you want to perform import/export operation")

    get_marketplaces = fields.Boolean("Marketplaces", help="Obtains available Marketplace from Shipstation")
    get_stores = fields.Boolean("Stores", help="Obtains the list of installed stores on the account.")
    get_carrier = fields.Boolean("Carriers", help="Obtains the list of installed carrier on the account.")
    get_carrier_services = fields.Boolean("Carrier Services", help="Obtains the list of carrier services on the account")
    get_customer = fields.Boolean("Customers", help="Obtains the list of Customer on the account")
    get_warehouse = fields.Boolean("Warehouse", help="Obtains the list of warehouse on the account")
    get_product = fields.Boolean("Product", help="Obtains the list of product on the account")
    get_order = fields.Boolean("Orders", help="Obtains a list of orders")

    @api.model
    def default_get(self, fields):
        res = super(ImportExportOperation, self).default_get(fields)
        accounts = self.env['shipstation.accounts'].search([])
        res.update({'account_ids': [(6, 0, accounts.ids)]})
        return res

    def process_operation(self):
        for account in self.account_ids:
            if self.get_marketplaces:
                account.import_marketplaces()
            if self.get_stores:
                account.import_stores()
            if self.get_carrier:
                account.import_carrier()
            if self.get_carrier_services:
                account.carrier_services()
            if self.get_customer:
                account.import_customer()
            if self.get_order:
                account.import_orders()
            if self.get_product:
                account.import_products()
            if self.get_warehouse:
                account.import_warehouse()
        return True
