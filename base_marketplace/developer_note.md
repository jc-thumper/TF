Generic Methods
---------------
##### Notification:
###### Syntax:
```
def is_product_import_notification_message(self, count, marketplace)
    return title, message

self.send_smart_notification('is_order_create', 'success', 5)
```

##### Schedule Actions:
###### Syntax:

Add this method to Marketplace app.

```
def shopify_setup_schedule_actions(self, mk_instance_id):
    cron_name = '{} : Auto Import Shopify Sale Order'.format(mk_instance_id.name)
    self.create_marketplace_cron(mk_instance_id, cron_name, method_name='cron_auto_import_shopify_orders', model_name='sale.order', minutes=15)
    cron_name = '{} : Auto Update Shopify Sale Order'.format(mk_instance_id.name)
    self.create_marketplace_cron(mk_instance_id, cron_name, method_name='cron_auto_update_order_status', model_name='sale.order', minutes=25)
    cron_name = '{} : Auto Export Shopify Product\'s Stock'.format(mk_instance_id.name)
    self.create_marketplace_cron(mk_instance_id, cron_name, method_name='cron_auto_export_stock', model_name='shopify.product.template.ts', minutes=35)
    return True
```

##### Marketplace Log Creation:
Base method of marketplace to check validation of product while importing according to instance configuration.
###### Method:
```
mk_log_id = self.env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, operation_type='import')
mk_log_line_dict['success'].append({'log_message': 'IMPORT LISTING: {} successfully created'.format(mk_listing_id.name)})
```

Useful Methods
---------------
##### Get Stock:
###### Method: 
It will give you stock according to marketplace configuration
```
def get_product_stock(self, export_qty_type, export_qty_value, warehouse_id, stock_type)
```

##### Get Odoo Variant and Listing Item:
It will give you Odoo Variant and Listing Item according to marketplace Configuration
###### Method:
```
def get_odoo_product_variant_and_listing_item(self, variant_id, mk_instance_id, variant_barcode, variant_sku)
```

##### Check for validation for product while import process:
Base method of marketplace to check validation of product while importing according to instance configuration.
###### Method:
```
listing_item_validation_dict = {'title': 'title', 'id': 'id', 'variants': [{'sku': 'sku', 'barcode': 'barcode'}]}
is_import, log_message = self.check_validation_for_import_product(mk_instance_id.sync_product_with, listing_item_validation_dict, odoo_product_id, listing_item_id)
```

##### Get Odoo Tax:
Base method of marketplace that will return created text list.
###### Method:
```
tax_lines = [{'rate': 'rate', 'title': 'title'}]
def get_odoo_tax(self, mk_instance_id, tax_lines, taxes_included):
    return [(6, 0, tax_list)]
```

##### Create Activity:
Base method of marketplace that will create activity based on instance configuration.
###### Method:
```
Here self is recordset of mk.queue.job
self.create_activity_action("Activity Note")
```

##### Create Log and attach it with Queue Job and Queue Job line:
Base method of marketplace that will create log and log line.
###### Method:
```
Please check any app example
```

##### Set default API limit according to the Marketplace:
Set default api fetch limit according to marketplace. Need to add method <marketplace_name>_mk_default_api_limit and return integer value.  
###### Method:
```
def shopify_mk_default_api_limit(self):
    return 250
```
