import pytz
import hashlib
from datetime import timedelta
from odoo import api, models, fields, _
from odoo.exceptions import UserError


class MarketplaceOperation(models.TransientModel):
    _name = "mk.operation"
    _description = "Marketplace Operation"

    def _get_default_from_date(self):
        mk_instance_id = self.env.context.get('active_id')
        mk_instance_id = self.env['mk.instance'].search([('id', '=', mk_instance_id)], limit=1)
        from_date = mk_instance_id.last_order_sync_date if mk_instance_id.last_order_sync_date else fields.Datetime.now() - timedelta(3)
        from_date = fields.Datetime.to_string(from_date)
        return from_date

    def _get_default_to_date(self):
        to_date = fields.Datetime.now()
        to_date = fields.Datetime.to_string(to_date)
        return to_date

    def _get_default_marketplace(self):
        if 'default_marketplace_instance_id' in self.env.context:
            instance_id = self.env.context.get('active_id', False)
        else:
            instance_id = self.env['mk.instance'].search([('state', '=', 'confirmed')], limit=1).id
        return instance_id

    def _get_default_marketplaces(self):
        if 'default_marketplace_instance_id' in self.env.context:
            instance_ids = self.env.context.get('active_ids', False)
        else:
            instance_ids = self.env['mk.instance'].search([('state', '=', 'confirmed')]).ids
        return instance_ids

    mk_instance_ids = fields.Many2many("mk.instance", 'mk_instance_operation_rel', 'instance_id', 'operation_id', string="Marketplaces", domain=[('state', '=', 'confirmed')],
                                       default=_get_default_marketplaces)
    mk_instance_id = fields.Many2one("mk.instance", string="Marketplace", domain=[('state', '=', 'confirmed')], default=_get_default_marketplace)
    marketplace = fields.Selection(related="mk_instance_id.marketplace", string='Marketplace Name')

    # Marketplace Export Fields
    import_customers = fields.Boolean("Import Customers")
    import_products = fields.Boolean("Import Listing")
    update_product_price = fields.Boolean("Update Product Price")
    import_stock = fields.Boolean("Import Stock")
    import_orders = fields.Boolean("Import Sale Orders")
    from_date = fields.Datetime("From Date", default=_get_default_from_date)
    to_date = fields.Datetime("To Date", default=_get_default_to_date)
    mk_listing_id = fields.Char("Marketplace Listing ID", help="Used to import specific Product from Marketplace using Marketplace ID.")
    mk_order_id = fields.Char("Marketplace Order ID", help="Used to import specific Order from Marketplace using Marketplace ID.")

    # Marketplace Export Fields
    is_update_order_status = fields.Boolean("Update Order Status")
    is_set_price = fields.Boolean("Set Price?")
    is_set_quantity = fields.Boolean("Set Quantity?")
    is_update_product = fields.Boolean("Update Detail?", default=True)
    is_publish_in_store = fields.Boolean("Publish in Store?")
    is_set_images = fields.Boolean("Set Images?")
    is_export_products = fields.Boolean("Export Products?")
    is_update_products = fields.Boolean("Update Products?")

    @api.model
    def default_get(self, default_fields):
        res = super(MarketplaceOperation, self).default_get(default_fields)
        active_model = self._context.get('active_model')
        active_ids = self._context.get('active_ids')
        if active_model == 'mk.listing' and active_ids:
            listing = self.env[active_model].browse(active_ids)
            if len(listing.mapped('mk_instance_id')) > 1:
                raise UserError(_('Operation not allowed! Make sure selected listing belongs to only one instance'))
        return res

    def do_import_operations(self):
        if not self.mk_instance_id:
            raise UserError(_("Please select marketplace instance to process."))
        instance = self.mk_instance_id
        if self.import_customers:
            if hasattr(self.env['res.partner'], '%s_import_customers' % instance.marketplace):
                getattr(self.env['res.partner'], '%s_import_customers' % instance.marketplace)(instance)
        if self.import_products:
            if hasattr(self.env['mk.listing'], '%s_import_listings' % instance.marketplace):
                getattr(self.env['mk.listing'], '%s_import_listings' % instance.marketplace)(instance, mk_listing_id=self.mk_listing_id)
        if self.import_orders:
            if hasattr(self.env['sale.order'], '%s_import_orders' % instance.marketplace):
                getattr(self.env['sale.order'], '%s_import_orders' % instance.marketplace)(instance, self.from_date, self.to_date, mk_order_id=self.mk_order_id)
        if self.import_stock:
            if hasattr(self.env['mk.listing'], '%s_import_stock' % instance.marketplace):
                getattr(self.env['mk.listing'], '%s_import_stock' % instance.marketplace)(instance)

    def do_export_operations(self):
        if not self.mk_instance_id:
            raise UserError(_("Please select marketplace instance to process."))
        instance = self.mk_instance_id
        if self.is_export_products:
            self.export_listing_to_mk()
        if self.is_update_products:
            self.update_listing_to_mk()
        if self.is_set_price:
            if hasattr(self.env['mk.listing'], '%s_set_price' % instance.marketplace):
                getattr(self.env['mk.listing'], '%s_set_price' % instance.marketplace)(instance)
        if self.is_set_quantity:
            if hasattr(self.env['mk.listing'], '%s_set_quantity' % instance.marketplace):
                getattr(self.env['mk.listing'], '%s_set_quantity' % instance.marketplace)(instance)
        if self.is_set_images:
            if hasattr(self.env['mk.listing'], '%s_set_images' % instance.marketplace):
                getattr(self.env['mk.listing'], '%s_set_images' % instance.marketplace)(instance)
        if self.is_update_order_status:
            if hasattr(self.env['sale.order'], '%s_update_order_status' % instance.marketplace):
                getattr(self.env['sale.order'], '%s_update_order_status' % instance.marketplace)(instance)

    def mk_add_to_listing(self):
        self.ensure_one()
        product_template_obj = self.env['product.template']
        product_active_ids = self._context.get('active_ids', [])
        odoo_template_ids = product_template_obj.search([('id', 'in', product_active_ids)])
        if not odoo_template_ids:
            raise UserError(_("SKU not found in Selected Products."))
        listing_ids = self.env['mk.listing']
        for instance in self.mk_instance_ids:
            for product_template in odoo_template_ids:
                if not all(product_template.product_variant_ids.mapped('default_code')):
                    raise UserError(_("Product : {} Internal Reference (SKU) is missing in some variant(s)! \n\nPlease set the unique internal reference in all variants".format(product_template.name)))
                listing_ids |= product_template.create_or_update_listing(instance)
        if listing_ids:
            action = self.env.ref('base_marketplace.action_marketplace_listing_all').read()[0]
            action['domain'] = [('id', 'in', listing_ids.ids)]
            return action
        return True

    def export_listing_to_mk(self):
        self.ensure_one()
        mk_listing_obj = self.env['mk.listing']
        if self._context.get('active_model') == 'mk.listing' and self._context.get('active_ids', []):
            listing_to_export = mk_listing_obj.search([('id', 'in', self._context.get('active_ids', [])), ('is_listed', '=', False)])
        else:
            listing_to_export = mk_listing_obj.search([('mk_instance_id', '=', self.mk_instance_id.id), ('is_listed', '=', False)])
        for listing in listing_to_export:
            if hasattr(listing, '%s_export_listing_to_mk' % listing.mk_instance_id.marketplace):
                getattr(listing, '%s_export_listing_to_mk' % listing.mk_instance_id.marketplace)(self)
        return True

    def update_listing_to_mk(self):
        self.ensure_one()
        mk_listing_obj = self.env['mk.listing']
        if self._context.get('active_model') == 'mk.listing' and self._context.get('active_ids', []):
            listing_to_update = mk_listing_obj.search([('id', 'in', self._context.get('active_ids', [])), ('is_listed', '=', True)])
        else:
            listing_to_update = mk_listing_obj.search([('mk_instance_id', '=', self.mk_instance_id.id), ('is_listed', '=', True)])
        for listing in listing_to_update:
            if hasattr(listing, '%s_update_listing_to_mk' % listing.mk_instance_id.marketplace):
                getattr(listing, '%s_update_listing_to_mk' % listing.mk_instance_id.marketplace)(self)
        return True
