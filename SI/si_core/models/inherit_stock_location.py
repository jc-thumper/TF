import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    ###############################
    # FIELDS
    ###############################
    ignore_compute_on_hand = fields.Boolean(_('Ignore To Compute Product Qty'), default=False)

    ###############################
    # HELPER FUNCTIONS
    ###############################
    def get_all_locations_of_warehouse(self, warehouse_id, company_id, is_excluded_location=True):
        result = []
        StockWarehouse = self.env['stock.warehouse']
        StockLocation = self.env['stock.location']
        Product = self.env['product.product']

        location_ids = [w.view_location_id.id for w in StockWarehouse.browse([warehouse_id])]
        if location_ids:
            # get all locations of selected warehouse
            domain_quant_loc, _, _ = Product._get_domain_locations_new(
                location_ids=location_ids, company_id=company_id, compute_child=True)

            all_locations_in_warehouse = StockLocation.search(domain_quant_loc).ids
            if is_excluded_location is True:
                excluded_location_ids = self.get_excluded_locations()
                result = list(set(all_locations_in_warehouse) - set(excluded_location_ids))
            else:
                result = all_locations_in_warehouse

        return result

    def get_excluded_locations(self):
        result = self.search([('ignore_compute_on_hand', '=', True)]).ids
        return result
