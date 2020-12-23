import ast
from odoo import models, fields, _

EXPORT_QTY_TYPE = [('fix', 'Fix'), ('percentage', 'Percentage')]


class MkListingItem(models.Model):
    _name = "mk.listing.item"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Marketplace Listing Items'

    def _compute_sales_price_with_currency(self):
        for record in self:
            instance_id = record.mk_instance_id or record.mk_listing_id.mk_instance_id
            pricelist_item_id = self.env['product.pricelist.item'].search([('pricelist_id', '=', instance_id.pricelist_id.id), ('product_id', '=', record.product_id.id)], order='id', limit=1)
            record.sale_price = pricelist_item_id.fixed_price or False
            record.currency_id = pricelist_item_id.currency_id.id or False

    name = fields.Char('Name', required=True)
    sequence = fields.Integer(help="Determine the display order", default=10)
    mk_id = fields.Char("Marketplace Identification", copy=False)
    product_id = fields.Many2one('product.product', string='Product', ondelete='cascade')
    mk_listing_id = fields.Many2one('mk.listing', "Listing", ondelete="cascade")
    mk_instance_id = fields.Many2one('mk.instance', "Instance", ondelete='cascade')
    marketplace = fields.Selection(related="mk_instance_id.marketplace", string='Marketplace')
    default_code = fields.Char('Internal Reference', track_visibility='onchange')
    barcode = fields.Char('Barcode', copy=False, help="International Article Number used for product identification.")
    item_create_date = fields.Datetime("Creation Date", readonly=True, index=True)
    item_update_date = fields.Datetime("Updated On", readonly=True)
    is_listed = fields.Boolean("Listed?", copy=False, track_visibility='onchange')
    export_qty_type = fields.Selection(EXPORT_QTY_TYPE, string="Export Qty Type")
    export_qty_value = fields.Float("Export Qty Value")
    image_ids = fields.Many2many('mk.listing.image', 'mk_listing_image_listing_rel', 'listing_item_id', 'mk_listing_image_id', string="Images")
    sale_price = fields.Monetary(compute="_compute_sales_price_with_currency", currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', compute="_compute_sales_price_with_currency")

    def create_or_update_pricelist_item(self, variant_price):
        self.ensure_one()
        instance_id = self.mk_instance_id or self.mk_listing_id.mk_instance_id
        pricelist_currency = instance_id.pricelist_id.currency_id
        if pricelist_currency != self.product_id.product_tmpl_id.company_id.currency_id:
            variant_price = pricelist_currency.compute(variant_price, self.product_id.product_tmpl_id.company_id.currency_id)
        pricelist_item_id = self.env['product.pricelist.item'].search([('pricelist_id', '=', instance_id.pricelist_id.id), ('product_id', '=', self.product_id.id)], limit=1)
        if pricelist_item_id:
            pricelist_item_id.write({'fixed_price': variant_price})
        else:
            instance_id.pricelist_id.write({'item_ids': [(0, 0, {
                'applied_on': '0_product_variant',
                'product_id': self.product_id.id,
                'product_tmpl_id': self.product_id.product_tmpl_id.id,
                'compute_price': 'fixed',
                'fixed_price': variant_price
            })]})
        return True

    def action_change_listing_item_price(self):
        action = self.env.ref('base_marketplace.action_product_pricelistitem_mk').read()[0]
        custom_view_id = False
        if hasattr(self, '%s_action_change_listing_item_view' % self.mk_instance_id.marketplace):
            custom_view_id = getattr(self, '%s_action_change_listing_item_view' % self.mk_instance_id.marketplace)()
        context = self._context.copy()
        if 'context' in action and type(action['context']) == str:
            context.update(ast.literal_eval(action['context']))
        else:
            context.update(action.get('context', {}))
        action['context'] = context
        action['context'].update({
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_product_id': self.product_id.id,
            'default_applied_on': '0_product_variant',
            'default_compute_price': 'fixed',
            'default_pricelist_id': self.mk_instance_id.pricelist_id.id,
        })
        if custom_view_id:
            action['views'] = [(custom_view_id.id, 'tree')]
        instance_id = self.mk_instance_id or self.mk_listing_id.mk_instance_id
        action['domain'] = [('pricelist_id', '=', instance_id.pricelist_id.id), ('product_id', '=', self.product_id.id)]
        return action
