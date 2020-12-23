13.0.0.2: 
- Visible Is Notify for fulfillment in instance view.
- Added note on Sale and Delivery Order for fulfillment.

13.0.0.3: 
- Improve product barcode and sku search algorithm. Fix update product issue.

13.0.0.4:
- Improve all of the import api request.
 
13.0.0.5: 
- Removed warnings shows in odoo.sh.

13.0.0.6: 
- Removed use of Deprecated method.
- Removed update_at_min from get product list while page_info is present in api call.
- Fixed the issue of wrong Product Template set in Marketplace Listing.
- Fixed second page api calling issue.
- Increase default api limit from 200 to 250.
- Fetch only Active Location from Shopify
- Reduce 1 API call while Update Stock in Shopify through Schedule Action.
- Set delay if API limit is exceed.

13.0.0.7:
- Improve variants search algorithm. Improve to import/sync product with different no. of variants in Odoo and Shopify.

13.0.0.8:
- Added delay if API limit in export Stock.
- Fix bug of create sale order even if product not found.

13.0.0.9:
- Auto set Fulfillment Status field at the time of instance creation.
- Added functionality to manage Shopify's Custom Product Line
- Improvement in Logs

13.0.0.10:
- Improve import listing Process.
- Fixed issue of product variation price update.

13.0.0.11:
- Fixed bug of Webhook.

13.0.1.0:
- Refactor import inventory flow totally.
- Added Automated Job that will import Inventory.
- Improved Queue line process and Log management.
- Ability to import multiple Products and Orders by adding comma separated ids. 
- Set weight in Odoo products if not set.

13.0.1.1:
- Improved fields visibility.
- Improved Import listing code.
- Changes Fulfillment Status Field's Type
- Change sql constraint to python constraint of financial workflow.
- Fixed issue of publish product from the Update Listing in Marketplace Popup.
- Fixed the issue of Import Product.
- Removed unnecessary fields and class.

13.0.1.2:
- Fixed bug of inventory Import.

13.0.1.3:
- Fixed bug of Order line Discount.

13.0.1.4:
- Fetch Orders based on Update order date instead of Create date.