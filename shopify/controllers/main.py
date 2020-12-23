import codecs
from .. import shopify
import logging
import psycopg2
from odoo.http import request
from odoo import api, http, registry, SUPERUSER_ID, _

_logger = logging.getLogger("Teqstars:Shopify")


class ShopifyWebhook(http.Controller):

    @http.route('/shopify/webhook/notification/<string:db_name>/<int:mk_instance_id>', type='json', auth="public", csrf=False)
    def shopify_webhook_process(self, db_name, mk_instance_id, **kwargs):
        webhook_type = request.httprequest.headers.get('X-Shopify-Topic', False)
        try:
            db_registry = registry(db_name)
            with db_registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                response = request.jsonrequest or {}
                mk_instance_id = env['mk.instance'].browse(int(mk_instance_id))
                if mk_instance_id.state != 'confirmed':
                    return {'status': 'Instance {} is not in Confirmed State.'.format(mk_instance_id.name)}
                mk_log_line_dict = env.context.get('mk_log_line_dict', {'error': [], 'success': []})
                try:
                    mk_log_id = env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, operation_type='webhook')
                    self.process_webhook_response(env, webhook_type, response, mk_instance_id, mk_log_id)
                except Exception as e:
                    log_message = "Error while processing Shopify webhook {}, ERROR: {}.".format(webhook_type, e)
                    mk_log_line_dict['error'].append({'log_message': 'WEBHOOK PROCESS: {}'.format(log_message)})
                finally:
                    env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, operation_type='webhook', mk_log_line_dict=mk_log_line_dict)
                    if not mk_log_id.log_line_ids:
                        mk_log_id.unlink()
        except psycopg2.Error as e:
            _logger.error(_("SHOPIFY WEBHOOK RECEIVE: Error while Processing webhook request. ERROR: {}".format(e)))
        return {'status': 'Successfully processed.'}

    def process_webhook_response(self, env, webhook_type, response, mk_instance_id, mk_log_id):
        mk_listing_obj = env['mk.listing']
        mk_instance_id.connection_to_shopify()
        mk_log_line_dict = env.context.get('mk_log_line_dict', {'error': [], 'success': []})
        if webhook_type in ['customers/create', 'customers/update']:
            env['res.partner'].with_context(mk_log_line_dict=mk_log_line_dict).create_update_shopify_customers(response, mk_instance_id)

        if webhook_type in ['collections/create', 'collections/update']:
            collection_obj = env['shopify.collection.ts']
            collection_type = 'automated' if 'disjunctive' in response else 'manual'
            collection_id = collection_obj.create_update_collections(response, collection_type, mk_instance_id)
            if collection_type == 'manual':
                shopify_collection = shopify.CustomCollection.find(collection_id.shopify_collection_id)
            else:
                shopify_collection = shopify.SmartCollection.find(collection_id.shopify_collection_id)
            shopify_product_list = collection_obj.sync_collection_products(shopify_collection, mk_instance_id)
            mk_listing_ids = mk_listing_obj.search([('mk_id', 'in', shopify_product_list), ('mk_instance_id', '=', mk_instance_id.id)])
            collection_id.write({'mk_listing_ids': [(6, 0, mk_listing_ids.ids)]})
            if collection_id:
                coll_type = 'Created' if webhook_type == 'collections/create' else 'Updated'
                log_message = "Successfully {type} {name} Collection.".format(type=coll_type, name=collection_id.name)
                mk_log_line_dict['success'].append({'log_message': '{} COLLECTION: {}'.format(coll_type.upper(), log_message)})

        if webhook_type == 'collections/delete':
            collection_obj = env['shopify.collection.ts']
            collection_id = collection_obj.search([('shopify_collection_id', '=', response.get('id')), ('mk_instance_id', '=', mk_instance_id.id)])
            collection_id_name = collection_id.name
            collection_id and collection_id.unlink()
            log_message = "Successfully Deleted Collection. Collection Name: {}, Collection ID: {}".format(collection_id_name, response.get('id'))
            mk_log_line_dict['success'].append({'log_message': 'DELETE COLLECTION: {}'.format(log_message)})

        if webhook_type in ["products/create", "products/update"]:
            mk_listing_obj = env['mk.listing']
            update_product_price = True if webhook_type == 'products/create' else False
            mk_listing_id = mk_listing_obj.with_context(mk_log_line_dict=mk_log_line_dict).create_update_shopify_product(response, mk_instance_id,
                                                                                                                         update_product_price=update_product_price)
            if mk_listing_id:
                if mk_instance_id.is_sync_images:
                    mk_listing_obj.sync_product_image_from_shopify(mk_instance_id, mk_listing_id, response)

        if webhook_type == 'products/delete':
            mk_listing_obj = env['mk.listing']
            listing_id = mk_listing_obj.search([('mk_id', '=', response.get('id')), ('mk_instance_id', '=', mk_instance_id.id)])
            listing_name = listing_id.name
            listing_id and listing_id.unlink()
            log_message = "Successfully Deleted Listing. Listing Name: {}, Listing ID: {}".format(listing_name, response.get('id'))
            mk_log_line_dict['success'].append({'log_message': 'DELETE PRODUCT: {}'.format(log_message)})

        if webhook_type == 'orders/create':
            order_id = env['sale.order'].with_context(operation_type='webhook').process_import_order_from_shopify_ts(response, mk_instance_id)
            if order_id:
                log_message = "Successfully imported marketplace order {}.".format(order_id.mk_order_number)
                mk_log_line_dict['success'].append({'log_message': 'IMPORT ORDER: {}'.format(log_message)})
        env['mk.log'].create_update_log(mk_instance_id=mk_instance_id, mk_log_id=mk_log_id, mk_log_line_dict=mk_log_line_dict)
        return True
