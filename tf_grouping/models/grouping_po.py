from odoo import api, fields, models, _, SUPERUSER_ID

import logging
_logger = logging.getLogger(__name__)


class PurchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    bom_origin_id = fields.Char(string="Bill of Material Origin")


class PurchaseStockInherit(models.Model):
    _inherit = 'stock.rule'

    def _make_po_get_domain(self, company_id, values, partner):
        domain = super()._make_po_get_domain(company_id, values, partner)

        if self.env.company.allow_grouping_bom and partner.id in self.env.company.vendor_ids.ids:
            if values.get('move_dest_ids') and values.get('move_dest_ids')[:1] \
                    and values.get('move_dest_ids')[:1].bom_origin_id:
                domain = domain + (('bom_origin_id', '=', values.get('move_dest_ids')[:1].bom_origin_id),)
        return domain

    def _prepare_purchase_order(self, company_id, origins, values):
        vals = super()._prepare_purchase_order(company_id, origins, values)

        if self.env.company.allow_grouping_bom:
            if values[0].get('move_dest_ids') and values[0].get('move_dest_ids')[:1] \
                    and values[0].get('move_dest_ids')[:1][0].bom_origin_id:
                vals.update({'bom_origin_id': values[0].get('move_dest_ids')[:1][0].bom_origin_id})
        return vals
