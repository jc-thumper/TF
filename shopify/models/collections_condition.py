from odoo import models, fields

COLUMN_SELECTION = [('title', 'Title',),
                    ('type', 'Type',),
                    ('vendor', 'Vendor',),
                    ('variant_title', 'Variant Title',),
                    ('variant_compare_at_price', 'Variant Compare at Price',),
                    ('variant_weight', 'Variant Weight',),
                    ('variant_inventory', 'Variant Inventory',),
                    ('variant_price', 'Variant Price'),
                    ('tag', 'Tag')]

RELATION_SELECTION = [('greater_than', 'greater_than'),
                      ('less_than', 'less_than'),
                      ('equals', 'equals'),
                      ('not_equals', 'not_equals'),
                      ('starts_with', 'starts_with'),
                      ('ends_with', 'ends_with'),
                      ('contains', 'contains'),
                      ('not_contains', 'not_contains')]


class ShopifyCollectionCondition(models.Model):
    _name = "shopify.collection.condition.ts"
    _description = "Shopify Collection Condition"

    column = fields.Selection(COLUMN_SELECTION, "Column",
                              help="The property of a product being used to populate the smart collection.")
    relation = fields.Selection(RELATION_SELECTION, "Relation",
                                help="The relationship between the column choice, and the condition")
    condition = fields.Char("Condition", help="Select products for a smart collection using a condition. "
                                              "Values are either strings or numbers, depending on the relation value.")
    shopify_collection_id = fields.Many2one("shopify.collection.ts", "Collection ID")
