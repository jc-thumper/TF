from odoo import models, fields, api


class ShipstationWarehouse(models.Model):
    _name = 'shipstation.warehouse'
    _description = 'Shipstation Warehouse'

    name = fields.Char(string='Name', required=True)
    shipstation_id = fields.Integer(string='Shipstation Identification')
    account_id = fields.Many2one("shipstation.accounts", "Accounts", required=True, ondelete='restrict',
                                 help="Account in which warehouse is configured")
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', ondelete='restrict')

    is_default = fields.Boolean(string='Is Default')
    origin_address_id = fields.Many2one('res.partner', string="Origin Address")
    return_address_id = fields.Many2one('res.partner', string="Return Address")

    def import_warehouse(self, account=False):
        res_partner_obj = self.env['res.partner']
        if not account:
            raise Warning("Shipstation Account not defined to import Warehouse list")
        response = account._send_request('warehouses', {})
        for warehouse in response:
            origin_address_dict = warehouse.get('originAddress')
            return_address_dict = warehouse.get('returnAddress')
            shipstation_id = warehouse.get('warehouseId')
            origin_address_id = res_partner_obj.ss_find_existing_or_create_partner(origin_address_dict, company=account.company_id)
            return_address_id = res_partner_obj.ss_find_existing_or_create_partner(return_address_dict, company=account.company_id)
            prepared_vals = {
                'name': warehouse.get('warehouseName', False),
                'is_default': warehouse.get('isDefault', False),
                'shipstation_id': shipstation_id,
                'account_id': account.id,
                'origin_address_id': origin_address_id.id,
                'return_address_id': return_address_id.id
            }
            existing_carrier = self.search([('shipstation_id', '=', shipstation_id)], limit=1)
            if existing_carrier:
                existing_carrier.write(prepared_vals)
            else:
                self.create(prepared_vals)
        return True