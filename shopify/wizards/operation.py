from odoo import models, fields


class MarketplaceOperation(models.TransientModel):
    _inherit = "mk.operation"

    # Marketplace Import Fields
    import_collections = fields.Boolean("Import Collections")

    # Marketplace Export Fields
    is_export_collection = fields.Boolean("Export Collections?")
    is_update_collection = fields.Boolean("Update Collections?")

    def do_import_operations(self):
        res = super(MarketplaceOperation, self).do_import_operations()
        if self.mk_instance_id and self.marketplace == 'shopify' and self.import_collections:
            self.env['shopify.collection.ts'].import_shopify_collections(self.mk_instance_id)
        return res

    def do_export_operations(self):
        res = super(MarketplaceOperation, self).do_export_operations()
        collection_obj = self.env["shopify.collection.ts"]
        if self.mk_instance_id and self.marketplace == 'shopify' and self.is_export_collection:
            collection_domain = [('mk_instance_id', '=', self.mk_instance_id.id), ('exported_in_shopify', '=', False)]
            collection_ids = collection_obj.search(collection_domain)
            collection_ids and collection_ids.export_collection_to_shopify_ts()
        if self.mk_instance_id and self.marketplace == 'shopify' and self.is_update_collection:
            collection_domain = [('mk_instance_id', '=', self.mk_instance_id.id), ('exported_in_shopify', '=', True)]
            collection_ids = collection_obj.search(collection_domain)
            collection_ids and collection_ids.update_collection_to_shopify_ts()
        return res
