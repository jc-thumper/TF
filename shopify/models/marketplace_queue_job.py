import pprint
from .. import shopify
from odoo import models, fields
from odoo.tools.safe_eval import safe_eval


class MkQueueJob(models.Model):
    _inherit = "mk.queue.job"

    def shopify_customer_queue_process(self):
        res_partner_obj, mk_instance_id = self.env['res.partner'], self.mk_instance_id
        draft_queue_line_ids = self.mk_queue_line_ids.filtered(lambda x: x.state == 'draft')
        for line in draft_queue_line_ids:
            customer_dict = safe_eval(line.data_to_process)
            res_partner_obj.with_context(queue_line_id=line, mk_log_id=line.queue_id.mk_log_id).create_update_shopify_customers(customer_dict, self.mk_instance_id)
            line.write({'processed_date': fields.Datetime.now()})
        return True

    def shopify_order_queue_process(self, skip_api_call=None):
        sale_order_obj, mk_instance_id = self.env['sale.order'], self.mk_instance_id
        shopify_location_obj, partner_obj = self.env['shopify.location.ts'], self.env['res.partner']
        draft_queue_line_ids = self.mk_queue_line_ids.filtered(lambda x: x.state == 'draft')
        if not skip_api_call:
            shopify_location_obj.import_location_from_shopify(mk_instance_id)
        for line in draft_queue_line_ids:
            shopify_order_dict = safe_eval(line.data_to_process)
            order_id = sale_order_obj.with_context(queue_line_id=line, skip_queue_change_state=True, mk_log_id=line.queue_id.mk_log_id).process_import_order_from_shopify_ts(
                shopify_order_dict, mk_instance_id)
            if order_id:
                line.write({'state': 'processed', 'processed_date': fields.Datetime.now()})
            else:
                line.write({'state': 'failed', 'processed_date': fields.Datetime.now()})
            self._cr.commit()
        if not self.env.context.get('hide_notification', False):
            error_count = self.env['mk.queue.job.line'].search_count([('state', '=', 'failed'), ('id', 'in', draft_queue_line_ids.ids)])
            success_count = self.env['mk.queue.job.line'].search_count([('state', '=', 'processed'), ('id', 'in', draft_queue_line_ids.ids)])
            mk_instance_id.send_smart_notification('is_order_create', 'error', error_count)
            mk_instance_id.send_smart_notification('is_order_create', 'success', success_count)
            if error_count:
                self.create_activity_action("Please check queue job for its fail reason.")

    def do_import_listing_process(self, listing_dict, mk_instance_id):
        listing_obj = self.env['mk.listing']
        mk_listing_id = listing_obj.create_update_shopify_product(listing_dict, mk_instance_id, update_product_price=True)
        if not mk_listing_id:
            return False
        if mk_instance_id.is_sync_images:
            listing_obj.sync_product_image_from_shopify(mk_instance_id, mk_listing_id, listing_dict)
        return True

    def shopify_product_queue_process(self):
        mk_instance_id, queue_job_line_obj = self.mk_instance_id, self.env['mk.queue.job.line']
        draft_queue_line_ids = self.mk_queue_line_ids.filtered(lambda x: x.state == 'draft')
        for line in draft_queue_line_ids:
            shopify_product_dict = safe_eval(line.data_to_process)
            processed = self.with_context(queue_line_id=line, mk_log_id=line.queue_id.mk_log_id).do_import_listing_process(shopify_product_dict, mk_instance_id)
            line.write({'processed_date': fields.Datetime.now(), 'state': 'processed' if processed else 'failed'})
            self._cr.commit()
        if not self.env.context.get('hide_notification', False):
            success_count = self.env['mk.queue.job.line'].search_count([('state', '=', 'processed'), ('id', 'in', draft_queue_line_ids.ids)])
            error_count = self.env['mk.queue.job.line'].search_count([('state', '=', 'failed'), ('id', 'in', draft_queue_line_ids.ids)])
            mk_instance_id.send_smart_notification('is_product_import', 'error', error_count)
            mk_instance_id.send_smart_notification('is_product_import', 'success', success_count)

    def shopify_product_retry_failed_queue(self):
        failed_queue_line_ids = self.mk_queue_line_ids.filtered(lambda ql: ql.state == 'failed')
        failed_queue_line_ids and failed_queue_line_ids.shopify_product_retry_failed_queue()
        return True

    def shopify_order_retry_failed_queue(self):
        failed_queue_line_ids = self.mk_queue_line_ids.filtered(lambda ql: ql.state == 'failed')
        failed_queue_line_ids and failed_queue_line_ids.shopify_order_retry_failed_queue()
        return True

    def shopify_customer_retry_failed_queue(self):
        failed_queue_line_ids = self.mk_queue_line_ids.filtered(lambda ql: ql.state == 'failed')
        failed_queue_line_ids and failed_queue_line_ids.shopify_customer_retry_failed_queue()
        return True


class MkQueueJobLine(models.Model):
    _inherit = "mk.queue.job.line"

    def shopify_product_retry_failed_queue(self):
        queue_id = self.mapped('queue_id')
        queue_id.mk_instance_id.connection_to_shopify()
        for line in self.filtered(lambda x: x.mk_id):
            shopify_product = shopify.Product().find(line.mk_id)
            shopify_product_dict = shopify_product.to_dict()
            line.write({'state': 'draft', 'data_to_process': pprint.pformat(shopify_product_dict)})
            line.queue_id.with_context(hide_notification=True).shopify_product_queue_process()
        return True

    def shopify_order_retry_failed_queue(self):
        queue_id = self.mapped('queue_id')
        queue_id.mk_instance_id.connection_to_shopify()
        for line in self.filtered(lambda x: x.mk_id):
            shopify_order = shopify.Order().find(line.mk_id)
            shopify_order_dict = shopify_order.to_dict()
            line.write({'state': 'draft', 'data_to_process': pprint.pformat(shopify_order_dict)})
            line.queue_id.with_context(hide_notification=True).shopify_order_queue_process(skip_api_call=True)
        return True

    def shopify_customer_retry_failed_queue(self):
        queue_id = self.mapped('queue_id')
        queue_id.mk_instance_id.connection_to_shopify()
        for line in self.filtered(lambda x: x.mk_id):
            shopify_customer = shopify.Customer().find(line.mk_id)
            shopify_customer_dict = shopify_customer.to_dict()
            line.write({'state': 'draft', 'data_to_process': pprint.pformat(shopify_customer_dict)})
            line.queue_id.with_context(hide_notification=True).shopify_customer_queue_process()
        return True
