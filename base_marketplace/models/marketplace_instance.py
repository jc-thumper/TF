import json
import babel
import random
import base64
from lxml import etree
from odoo.osv import expression
from odoo.tools import date_utils
from datetime import date, timedelta
from odoo import models, fields, api, _
from odoo.tools.misc import format_date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError, ValidationError
from babel.dates import format_date as babel_format_date
from babel.dates import get_quarter_names, format_datetime


class MkInstance(models.Model):
    _name = "mk.instance"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Marketplace Instance'

    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_month'}

    def _get_kanban_graph(self):
        self.dashboard_graph = json.dumps(self.get_bar_graph_datas())

    def _get_mk_kanban_badge_color(self):
        default_code = "#7C7BAD"
        # Hook type method that will get default kanban badge color according to marketplace type.
        if hasattr(self, '%s_mk_kanban_badge_color' % self.marketplace):
            default_code = getattr(self, '%s_mk_kanban_badge_color' % self.marketplace)
        return default_code

    def _get_mk_default_api_limit(self):
        api_limit = 200
        # Hook type method that will get default api limit according to marketplace type.
        if hasattr(self, '%s_mk_default_api_limit' % self.marketplace):
            api_limit = getattr(self, '%s_mk_default_api_limit' % self.marketplace)
        return api_limit

    def _get_mk_kanban_counts(self):
        for mk_instance_id in self:
            mk_instance_id.mk_listing_count = len(mk_instance_id.mk_listing_ids)
            mk_instance_id.mk_order_count = self.env['sale.order'].search_count([('mk_instance_id', '=', mk_instance_id.id)])
            mk_instance_id.mk_invoice_count = self.env['account.move'].search_count([('mk_instance_id', '=', mk_instance_id.id)])
            mk_instance_id.mk_shipment_count = self.env['stock.picking'].search_count([('mk_instance_id', '=', mk_instance_id.id)])
            mk_instance_id.mk_queue_count = len(mk_instance_id.mk_queue_ids.filtered(lambda x: x.state != 'processed'))
            mk_instance_id.mk_customer_count = self.env['res.partner'].search_count([('mk_instance_ids', 'in', mk_instance_id.ids), ('parent_id', '=', False)])  # not consider child partners.
            select_sql_clause, query_args = mk_instance_id._get_bar_graph_select_query()
            self.env.cr.execute(select_sql_clause, query_args)
            query_results = self.env.cr.dictfetchone()
            mk_instance_id.mk_total_revenue = query_results.get('total', 0.0)

    def _kanban_dashboard_graph(self):
        for mk_instance_id in self:
            chart_data = mk_instance_id.get_bar_graph_datas()
            mk_instance_id.kanban_dashboard_graph = json.dumps(chart_data)
            mk_instance_id.is_sample_data = chart_data[0].get('is_sample_data', False)

    def _get_discount_product(self):
        # Hook type method that will get default discount according to marketplace type.
        discount_product = False
        if hasattr(self, '_get_%s_discount_product' % self.marketplace):
            discount_product = getattr(self, '_get_%s_discount_product' % self.marketplace)
        return discount_product

    def _get_delivery_product(self):
        # Hook type method that will get default discount according to marketplace type.
        delivery_product = False
        if hasattr(self, '_get_%s_delivery_product' % self.marketplace):
            delivery_product = getattr(self, '_get_%s_delivery_product' % self.marketplace)
        return delivery_product

    def _get_default_warehouse(self):
        company_id = self.company_id if self.company_id else self.env.company
        warehouse_id = self.env['stock.warehouse'].search([('company_id', '=', company_id.id)], limit=1)
        return warehouse_id.id if warehouse_id else False

    @api.model
    def _lang_get(self):
        return self.env['res.lang'].get_installed()

    # TODO: Is environment needed?
    name = fields.Char(string='Name', required=True, help="Name of your marketplace instance.")
    color = fields.Integer('Color Index')
    marketplace = fields.Selection(selection=[], required=True, string='Marketplace')
    state = fields.Selection(selection=[('draft', 'Draft'), ('confirmed', 'Confirmed'), ('error', 'Error')], default='draft', track_visibility='onchange')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id)
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env.company.country_id)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True, default=_get_default_warehouse)
    api_limit = fields.Integer("API Record Count", default=_get_mk_default_api_limit, help="Record limit while perform api calling.")
    kanban_badge_color = fields.Char(default=_get_mk_kanban_badge_color)
    log_level = fields.Selection([('all', 'All'), ('success', 'Success'), ('error', 'Error')], string="Log Level", default="error")
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency")
    show_in_systray = fields.Boolean("Show in Systray Menu?", copy=False)
    queue_batch_limit = fields.Integer("Queue Batch Limit", default=100, help="Odoo will create a batch with defined limit.")
    image = fields.Binary("Marketplace Image", attachment=True, help="This field holds the image used as photo for the marketplace, limited to 1024x1024px.")
    image_medium = fields.Binary("Medium-sized photo", related="image", max_width=128, max_height=128, store=True,
                                 help="Medium-sized photo of the marketplace. It is automatically resized as a 128x128px image, with aspect ratio preserved. ")
    image_small = fields.Binary("Small-sized photo", related="image", max_width=64, max_height=64, store=True,
                                help="Small-sized photo of the marketplace. It is automatically resized as a 64x64px image, with aspect ratio preserved. ")
    lang = fields.Selection(_lang_get, string='Language', default=lambda self: self.env.lang, help="Instance language.")

    # Product Fields
    is_create_products = fields.Boolean("Create Odoo Products?", help="If Odoo products not found while Sync create Odoo products.")
    is_update_odoo_product_category = fields.Boolean("Update Category in Odoo Products?", help="Update Odoo Products Category.")
    is_sync_images = fields.Boolean("Sync Product Images?", help="If true then Images will be sync at the time of Import Listing.")
    sync_product_with = fields.Selection([('barcode', 'Barcode'), ('sku', 'SKU'), ('barcode_or_sku', 'Barcode or SKU')], string="Sync Product With", default="barcode_or_sku")
    last_listing_import_date = fields.Datetime("Last Listing Imported On", copy=False)

    # Stock Fields
    stock_field_id = fields.Many2one('ir.model.fields', string='Stock Based On', help="At the time of Export/Update inventory this field is used.",
                                     default=lambda self: self.env['ir.model.fields'].search([('model_id.model', '=', 'product.product'), ('name', '=', 'qty_available')]))
    last_stock_update_date = fields.Datetime("Last Stock Exported On", copy=False, help="Date were stock updated to marketplace.")
    last_stock_import_date = fields.Datetime("Last Stock Imported On", copy=False, help="Date were stock imported from marketplace.")
    is_validate_adjustment = fields.Boolean("Validate Inventory Adjustment?", help="If true then validate Inventory adjustment at the time of Import Stock Operation.")

    # Order Fields
    use_marketplace_sequence = fields.Boolean("Use Marketplace Order Sequence?", default=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', default=lambda self: self.env['crm.team'].search([], limit=1), help='Sales Team used for imported order.')
    discount_product_id = fields.Many2one('product.product', string='Discount Product', domain=[('type', '=', 'service')],
                                          help='Discount product used in sale order line.')
    delivery_product_id = fields.Many2one('product.product', string='Delivery Product', domain=[('type', '=', 'service')], help="""Delivery product used in sale order line.""")
    last_order_sync_date = fields.Datetime("Last Order Imported On", copy=False)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    tax_account_id = fields.Many2one('account.account', domain=[('deprecated', '=', False)], string='Tax Account', help="Account that will be set while creating tax.")
    tax_refund_account_id = fields.Many2one('account.account', domain=[('deprecated', '=', False)], string='Tax Account on Credit Notes',
                                            help="Account that will be set while creating tax.")

    # Customer Fields
    account_receivable_id = fields.Many2one('account.account', string='Receivable Account', domain="[('deprecated', '=', False), ('internal_type', '=', 'receivable')]",
                                            help="While creating Customer set this field in Account Receivable instead of default.")  # ('internal_type', '=', 'receivable'),
    account_payable_id = fields.Many2one('account.account', string='Payable Account', domain="[('deprecated', '=', False), ('internal_type', '=', 'payable')]",
                                         help="While creating Customer set this field in Account Payable instead of default.")  # ('internal_type', '=', 'payable'),
    last_customer_import_date = fields.Datetime("Last Customers Imported On", copy=False)

    # Scheduled actions
    cron_ids = fields.One2many("ir.cron", "mk_instance_id", "Automated Actions", context={'active_test': False})

    # Emails & Notifications
    notification_ids = fields.One2many("mk.notification", "mk_instance_id", "Marketplace Notification")

    # Dashboard Fields
    mk_listing_ids = fields.One2many('mk.listing', 'mk_instance_id', string="Listing")
    mk_listing_count = fields.Integer("Listing Count", compute='_get_mk_kanban_counts')
    mk_order_ids = fields.One2many('sale.order', 'mk_instance_id', string="Orders")
    mk_order_count = fields.Integer("Order Count", compute='_get_mk_kanban_counts')
    mk_invoice_ids = fields.One2many('account.move', 'mk_instance_id', string="Invoices")
    mk_invoice_count = fields.Integer("Invoice Count", compute='_get_mk_kanban_counts')
    mk_total_revenue = fields.Float("Revenue", compute='_get_mk_kanban_counts')
    mk_shipment_ids = fields.One2many('stock.picking', 'mk_instance_id', string="Shipments")
    mk_shipment_count = fields.Integer("Shipment Count", compute='_get_mk_kanban_counts')
    mk_queue_ids = fields.One2many('mk.queue.job', 'mk_instance_id', string="Queue Job")
    mk_queue_count = fields.Integer("Queue Count", compute='_get_mk_kanban_counts')
    mk_customer_ids = fields.Many2many("res.partner", "mk_instance_res_partner_rel", "partner_id", "marketplace_id", string="Customers")

    mk_customer_count = fields.Integer("Customer Count", compute='_get_mk_kanban_counts')

    mk_log_ids = fields.One2many('mk.log', 'mk_instance_id', string="Logs")

    # Kanban bar graph
    kanban_dashboard_graph = fields.Text(compute='_kanban_dashboard_graph')

    # Activity
    mk_activity_type_id = fields.Many2one('mail.activity.type', string='Activity', domain="[('res_model_id', '=', False)]")
    activity_date_deadline_range = fields.Integer(string='Due Date In')
    activity_date_deadline_range_type = fields.Selection([('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months'), ], string='Due type', default='days')
    activity_user_ids = fields.Many2many('res.users', string='Responsible')

    is_sample_data = fields.Boolean("Is Sample Data", compute='_kanban_dashboard_graph')

    def get_all_marketplace(self):
        # marketplace_list = self.search([]).mapped('marketplace')
        marketplace_list = [marketplace[0] for marketplace in self.env['mk.instance'].fields_get()['marketplace']['selection'] if marketplace]
        return marketplace_list and marketplace_list or []

    @api.onchange('marketplace')
    def _onchange_marketplace(self):
        default_code, image = "#7C7BAD", False
        # Hook type method that will get default kanban badge color according to marketplace type.
        if hasattr(self, '%s_mk_kanban_badge_color' % self.marketplace):
            default_code = getattr(self, '%s_mk_kanban_badge_color' % self.marketplace)()
        self.kanban_badge_color = default_code
        if hasattr(self, '%s_mk_kanban_image' % self.marketplace):
            image_path = getattr(self, '%s_mk_kanban_image' % self.marketplace)()
            image = base64.b64encode(open(image_path, 'rb').read())
        if not self.delivery_product_id and hasattr(self, '_get_%s_delivery_product' % self.marketplace):
            self.delivery_product_id = getattr(self, '_get_%s_delivery_product' % self.marketplace)()
        if not self.discount_product_id and hasattr(self, '_get_%s_discount_product' % self.marketplace):
            self.discount_product_id = getattr(self, '_get_%s_discount_product' % self.marketplace)()
        self.image = image

    @api.model
    def create(self, vals):
        res = super(MkInstance, self).create(vals)
        self.env['ir.cron'].setup_schedule_actions(res)
        return res

    def write(self, vals):
        res = super(MkInstance, self).write(vals)
        return res

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, "[{}] {}".format(dict(record._fields['marketplace'].selection).get(record.marketplace), record.name or '')))
        return result

    def action_confirm(self):
        self.ensure_one()
        if hasattr(self, '%s_action_confirm' % self.marketplace):
            getattr(self, '%s_action_confirm' % self.marketplace)()
        self.write({'state': 'confirmed'})
        return True

    def reset_to_draft(self):
        self.write({'state': 'draft'})

    def get_marketplace_import_operation_wizard(self):
        if hasattr(self, '%s_marketplace_import_operation_wizard' % self.marketplace):
            return getattr(self, '%s_marketplace_import_operation_wizard' % self.marketplace)()
        else:
            return self.env.ref('base_marketplace.action_marketplace_import_operation').read()[0]

    def is_order_create_notification_message(self, count, marketplace):
        # Dynamic method for get notification title and message
        title = _('{marketplace} Orders Import'.format(marketplace=marketplace))
        message = {'error': '{count} {marketplace} order(s) facing issue for {instance} Instance'.format(count=count, marketplace=marketplace, instance=self.name), 'success': _(
            '{count} {marketplace} order(s) imported successfully for {instance} Instance.'.format(count=count, marketplace=marketplace, instance=self.name))}
        return title, message

    def is_product_import_notification_message(self, count, marketplace):
        # Dynamic method for get notification title and message
        title = _('{marketplace} Product Import'.format(marketplace=marketplace))
        message = {'error': '{count} {marketplace} product(s) facing issue for {instance} Instance'.format(count=count, marketplace=marketplace, instance=self.name),
                   'success': _('{count} {marketplace} product(s) imported successfully for {instance} Instance.'.format(count=count, marketplace=marketplace, instance=self.name))}
        return title, message

    def get_smart_notification_message(self, notify_field, count, marketplace):
        # Hook type method that will get notification title and message according to `notify_field`
        title, message = 'No Title', 'Nothing to display'
        if hasattr(self, '%s_notification_message' % notify_field):
            title, message = getattr(self, '%s_notification_message' % notify_field)(count, marketplace)
        return title, message

    def send_smart_notification(self, notify_field, notify_type, count):
        """ Method to send Smart Notification to Users that is configured in Marketplace Notification Tab.
        :param notify_field: order_create, product_create
        :param notify_type: success, error, all.
        :param count: count
        :return: True
        exp. : self.send_smart_notification('is_order_create', 'success', 5)
        """
        notification_ids = self.notification_ids
        for notification_id in notification_ids:
            if hasattr(notification_id, notify_field) and count > 0:
                notify = getattr(notification_id, notify_field)
                if notify_type == 'error' and notification_id.type not in ['error', 'all']:
                    continue
                if notify_type == 'success' and notification_id.type not in ['success', 'all']:
                    continue
                if notify:
                    marketplace = notification_id.mk_instance_id.marketplace
                    marketplace_name = dict(self._fields['marketplace'].selection).get(marketplace) or ''
                    title, message = self.get_smart_notification_message(notify_field, count, marketplace_name)
                    if title and message:
                        warning = False if notify_type == 'success' else True
                        message = message.get('success') if notify_type == 'success' else message.get('error')
                        self.env['bus.bus'].sendone(
                            (self._cr.dbname, 'res.partner', notification_id.user_id.partner_id.id),
                            {'type': 'simple_notification', 'title': title, 'message': message, 'sticky': notification_id.is_sticky, 'warning': warning})

    def action_create_queue(self, type):
        self.ensure_one()
        queue_obj = self.env['mk.queue.job']
        return queue_obj.create({'type': type, 'mk_instance_id': self.id})

    def _graph_title_and_key(self):
        return ['Total Selling', _('Total Selling')]

    def _get_bar_graph_select_query(self):
        """
        Returns a tuple containing the base SELECT SQL query used to gather
        the bar graph's data as its first element, and the arguments dictionary
        for it as its second.
        """
        # return ("""SELECT sum(amount_residual_signed) as total, min(date_invoice) as aggr_date
        #        FROM account_move
        #        WHERE mk_instance_id = %(mk_instance_id)s and state = 'paid'""", {'mk_instance_id': self.id})
        return ('''
                SELECT SUM(move.amount_total) AS total, MIN(invoice_date_due) AS aggr_date
                FROM account_move move
                WHERE move.mk_instance_id = %(mk_instance_id)s
                AND move.state = 'posted'
                AND move.invoice_payment_state = 'paid'
                AND move.type IN %(invoice_types)s
            ''', {
            'invoice_types': tuple(['out_invoice']),
            'mk_instance_id': self.id
        })

    def get_bar_graph_datas(self):
        data = []
        today = fields.Datetime.now(self)
        data.append({'label': _('Past'), 'value': 0.0, 'type': 'past'})
        day_of_week = int(format_datetime(today, 'e', locale=self._context.get('lang') or 'en_US'))
        first_day_of_week = today + timedelta(days=-day_of_week + 1)
        for i in range(-4, 1):
            if i == 0:
                label = _('This Week')
            else:
                start_week = first_day_of_week + timedelta(days=i * 7)
                end_week = start_week + timedelta(days=6)
                if start_week.month == end_week.month:
                    label = str(start_week.day) + '-' + str(end_week.day) + ' ' + babel_format_date(end_week, 'MMM', locale=self._context.get('lang') or 'en_US')
                else:
                    label = babel_format_date(start_week, 'd MMM', locale=self._context.get('lang') or 'en_US') + '-' + babel_format_date(end_week, 'd MMM',
                                                                                                                                          locale=self._context.get(
                                                                                                                                              'lang') or 'en_US')
            data.append({'label': label, 'value': 0.0, 'type': 'past' if i < 0 else 'future'})

        # Build SQL query to find amount aggregated by week
        (select_sql_clause, query_args) = self._get_bar_graph_select_query()
        query = ''
        o_start_date = today + timedelta(days=-day_of_week + 1)
        start_date = today + timedelta(days=-day_of_week + 1)
        for i in range(-4, 2):
            if i == -4:
                start_date = o_start_date + timedelta(days=i * 7)
                query += "(" + select_sql_clause + " and invoice_date_due < '" + start_date.strftime(DEFAULT_SERVER_DATE_FORMAT) + "')"
            else:
                next_date = o_start_date + timedelta(days=i * 7)
                query += " UNION ALL (" + select_sql_clause + " and invoice_date_due >= '" + start_date.strftime(
                    DEFAULT_SERVER_DATE_FORMAT) + "' and invoice_date_due < '" + next_date.strftime(DEFAULT_SERVER_DATE_FORMAT) + "')"
                start_date = next_date
        self.env.cr.execute(query, query_args)
        query_results = self.env.cr.dictfetchall()

        for index in range(0, len(query_results)):
            if query_results[index].get('aggr_date') != None:
                data[index]['value'] = query_results[index].get('total')

        # Added random Sample data for better visualization.
        is_sample_data = True
        for index in range(0, len(query_results)):
            if query_results[index].get('total') not in [None, 0.0]:
                is_sample_data = False
                data[index]['value'] = query_results[index].get('total')

        [graph_title, graph_key] = self._graph_title_and_key()

        if is_sample_data:
            for index in range(0, len(query_results)):
                data[index]['type'] = 'o_sample_data'
                # we use unrealistic values for the sample data
                data[index]['value'] = random.randint(0, 20)
                graph_key = _('Sample data')

        return [{'values': data, 'title': graph_title, 'key': graph_key, 'is_sample_data': is_sample_data}]

    def _format_currency_amount(self, amount, currency_id):
        currency_id = self.env['res.currency'].browse(currency_id)
        pre = post = u''
        if currency_id.position == 'before':
            pre = u'{symbol}\N{NO-BREAK SPACE}'.format(symbol=currency_id.symbol or '')
        else:
            post = u'\N{NO-BREAK SPACE}{symbol}'.format(symbol=currency_id.symbol or '')
        return u'{pre}{0}{post}'.format(amount, pre=pre, post=post)

    @api.model
    def systray_get_marketplaces(self):
        mk_instance_ids = []
        if self.env.user.has_group('base_marketplace.group_base_marketplace'):
            mk_instance_ids = self.env['mk.instance'].search_read([('show_in_systray', '=', True), ('state', '=', 'confirmed')],
                                                                  ['id', 'name', 'marketplace', 'image_medium', 'mk_order_count', 'mk_listing_count', 'mk_total_revenue',
                                                                   'company_currency_id'])
        user_activities = {}
        for mk_instance_dict in mk_instance_ids:
            user_activities[mk_instance_dict['id']] = {'id': mk_instance_dict['id'],
                                                       'name': mk_instance_dict['name'],
                                                       'model': 'mk.instance',
                                                       'type': mk_instance_dict['marketplace'],
                                                       'icon': mk_instance_dict['image_medium'],
                                                       'mk_order_count': mk_instance_dict['mk_order_count'],
                                                       'mk_listing_count': mk_instance_dict['mk_listing_count'],
                                                       'mk_total_revenue': self._format_currency_amount(mk_instance_dict['mk_total_revenue'],
                                                                                                        mk_instance_dict['company_currency_id'][0])}
        return list(user_activities.values())

    def action_marketplace_open_instance_view(self):
        form_id = self.env.ref('base_marketplace.marketplace_instance_form_view')
        action = {
            'name': _('Marketplace Instance'),
            'view_id': False,
            'res_model': 'mk.instance',
            'context': self._context,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(form_id.id, 'form')],
            'type': 'ir.actions.act_window',
        }
        return action

    def redirect_to_general_dashboard(self):
        if self.env.user.has_group('base_marketplace.group_base_marketplace_manager'):
            return self.env.ref('base_marketplace.backend_mk_general_dashboard').read()[0]
        return self.env.ref('base_marketplace.action_marketplace_dashboard').read()[0]

    def get_from_to_date(self, total_orders):
        date_from, date_to = False, False
        if total_orders:
            date_from = total_orders[0].date_order
            date_to = next(reversed(total_orders)).date_order
        return date_from, date_to

    def get_mk_dashboard_data(self, date_from, date_to, is_general_dashboard=True):
        country_dict, category_dict, mk_type_dict = {}, {}, {}
        dashboard_data_list = dict(currency_id=self.env.user.company_id.currency_id.id, is_general_dashboard=is_general_dashboard,
                                   sale_graph=[], best_sellers=[], category_graph=[], country_graph=[],
                                   summary=dict(total_orders=0, total_sales=0, pending_shipments=0, avg_order_value=0))

        total_orders = self.env['sale.order'].search([('date_order', '>=', date_from),
                                                      ('date_order', '<=', date_to),
                                                      ('state', 'in', ['sale', 'done']),
                                                      ('mk_instance_id', 'in', self.ids)], order="date_order")
        if not date_from or not date_to or not self:
            return dashboard_data_list
        date_date_from = fields.Date.from_string(date_from)
        date_date_to = fields.Date.from_string(date_to)

        sales_domain = [('state', 'in', ['sale', 'done']), ('order_id', 'in', total_orders.ids), ('date', '>=', date_from), ('date', '<=', date_to)]

        # Product-based computation
        report_product_lines = self.env['mk.sale.report'].read_group(domain=sales_domain + [('product_type', '!=', 'service')],
                                                                     fields=['product_tmpl_id', 'product_uom_qty', 'price_total'],
                                                                     groupby='product_tmpl_id', orderby='price_total desc', limit=10)

        for product_line in report_product_lines:
            product_tmpl_id = self.env['product.template'].browse(product_line['product_tmpl_id'][0])
            dashboard_data_list['best_sellers'].append({'id': product_tmpl_id.id,
                                                        'name': product_tmpl_id.name,
                                                        'qty': product_line['product_uom_qty'],
                                                        'sales': product_line['price_total']})

        # Sale Graph
        if not is_general_dashboard:
            sale_graph_data = self._compute_sale_graph(date_date_from, date_date_to, sales_domain)
            dashboard_data_list['sale_graph'] = {'series': [{'name': 'Total Amount', 'data': sale_graph_data[1]}], 'categories': sale_graph_data[0]}
        else:
            series_data_list, bar_categories, bar_data = [], [], []
            for mk_instance_id in self:
                instance_name = mk_instance_id.name
                sale_graph_data = self._compute_sale_graph(date_date_from, date_date_to, [('state', 'in', ['sale', 'done']), ('mk_instance_id', '=', mk_instance_id.id)])
                series_data_list.append({'name': instance_name, 'data': sale_graph_data[1]})
                bar_data.append({'name': instance_name, 'data': [round(sum(sale_graph_data[1]), 2)]})
                # bar_data.append(sum(sale_graph_data[1]))
                bar_categories.append(instance_name)

            dashboard_data_list['sale_graph'] = {'series': series_data_list, 'categories': sale_graph_data[0]}
            dashboard_data_list['bar_graph'] = {'series': bar_data, 'categories': bar_categories}

            # Marketplace Type wise selling
            mk_type_data = self.env['mk.sale.report'].read_group(domain=sales_domain,
                                                                 fields=['marketplace_type', 'price_total'],
                                                                 groupby='marketplace_type', orderby='price_total desc', limit=5)
            [mk_type_dict.update({dict(self._fields['marketplace'].selection).get(mk_type_line['marketplace_type']): mk_type_line['price_total']}) for mk_type_line in mk_type_data]
            dashboard_data_list['mk_revenue_pieChart'] = {'series': list(mk_type_dict.values()), 'labels': list(mk_type_dict.keys())}

        # Country wise selling
        country_lines = self.env['mk.sale.report'].read_group(domain=sales_domain,
                                                              fields=['country_id', 'price_total'],
                                                              groupby='country_id', orderby='price_total desc', limit=5)
        [country_dict.update({country_line['country_id'][1]: country_line['price_total']}) for country_line in country_lines if country_line.get('country_id')]
        dashboard_data_list['country_graph'] = {'series': list(country_dict.values()), 'labels': list(country_dict.keys())}

        # Category wise selling
        category_lines = self.env['mk.sale.report'].read_group(domain=sales_domain,
                                                               fields=['categ_id', 'price_total'],
                                                               groupby='categ_id', orderby='price_total desc', limit=5)
        [category_dict.update({category_line['categ_id'][1]: category_line['price_total']}) for category_line in category_lines]
        dashboard_data_list['category_graph'] = {'series': list(category_dict.values()), 'labels': list(category_dict.keys())}

        # Tiles Summery
        if not is_general_dashboard:
            total_sales = self.env['mk.sale.report'].read_group(domain=sales_domain, fields=['price_total'], groupby='mk_instance_id')
            total_sales = total_sales[0].get('price_total') if total_sales else 0
            to_ship_domain = [('mk_instance_id', 'in', self.ids)]
        else:
            total_sales = total_orders.mapped('amount_total')
            total_sales = sum(total_sales) if total_sales else 0
            dashboard_data_list['summary']['total_sales'] = total_sales
            to_ship_domain = [('mk_instance_id', '!=', False)]

        to_ship_count = self.env['stock.picking'].search_count(
            to_ship_domain + [('state', 'not in', ['cancel', 'done']), ('create_date', '>=', date_from), ('create_date', '<=', date_to)])
        dashboard_data_list['summary']['total_orders'] = len(total_orders)
        dashboard_data_list['summary']['pending_shipments'] = to_ship_count
        dashboard_data_list['summary']['total_sales'] = total_sales
        days_diff = fields.Date.from_string(date_to) - fields.Date.from_string(date_from)
        dashboard_data_list['summary']['avg_order_value'] = total_sales / (days_diff.days if days_diff.days else 1)
        return dashboard_data_list

    def _compute_sale_graph(self, date_from, date_to, sales_domain, previous=False):
        days_between = (date_to - date_from).days
        date_list = [(date_from + timedelta(days=x)) for x in range(0, days_between + 1)]

        daily_sales = self.env['mk.sale.report'].read_group(domain=sales_domain,
                                                            fields=['date', 'price_subtotal'],
                                                            groupby='date:day')

        daily_sales_dict = {p['date:day']: p['price_subtotal'] for p in daily_sales}

        sales_graph = [{
            '0': fields.Date.to_string(d) if not previous else fields.Date.to_string(d + timedelta(days=days_between)),
            # Respect read_group format in models.py
            '1': daily_sales_dict.get(babel.dates.format_date(d, format='dd MMM yyyy', locale=self.env.context.get('lang') or 'en_US'), 0)
        } for d in date_list]
        date_range = [item.get('0') for item in sales_graph]
        sale_amount = [item.get('1') for item in sales_graph]
        if len(date_range) == 1:  # FIX ME: Sale chart has facing issue of not showing line if date range is only one day. Apply temp fix for this.
            next_date = fields.Date.to_string(fields.Date.from_string(date_range[0]) + timedelta(1))
            date_range = date_range + [next_date]
            sale_amount = sale_amount + [0.0]
        return [date_range, sale_amount]

    def has_single_date_filter(self, options):
        return options['date'].get('date_from') is None

    def _get_dates_previous_period(self, options, period_vals):
        period_type = period_vals['period_type']
        date_from = period_vals['date_from']
        date_to = period_vals['date_to']

        if not date_from or not date_to:
            date = (date_from or date_to).replace(day=1) - timedelta(days=1)
            return self._get_dates_period(options, None, date, period_type=period_type)

        date_to = date_from - timedelta(days=1)
        if period_type == 'fiscalyear':
            company_fiscalyear_dates = self.env.user.company_id.compute_fiscalyear_dates(date_to)
            return self._get_dates_period(options, company_fiscalyear_dates['date_from'], company_fiscalyear_dates['date_to'])
        if period_type == 'month':
            return self._get_dates_period(options, *date_utils.get_month(date_to), period_type='month')
        if period_type == 'quarter':
            return self._get_dates_period(options, *date_utils.get_quarter(date_to), period_type='quarter')
        if period_type == 'year':
            return self._get_dates_period(options, *date_utils.get_fiscal_year(date_to), period_type='year')
        date_from = date_to - timedelta(days=(date_to - date_from).days)
        return self._get_dates_period(options, date_from, date_to)

    def _get_dates_period(self, options, date_from, date_to, period_type=None):
        def match(dt_from, dt_to):
            if self.has_single_date_filter(options):
                return (date_to or date_from) == dt_to
            else:
                return (dt_from, dt_to) == (date_from, date_to)

        string = None
        if not period_type:
            date = date_to or date_from
            company_fiscalyear_dates = self.env.user.company_id.compute_fiscalyear_dates(date)
            if match(company_fiscalyear_dates['date_from'], company_fiscalyear_dates['date_to']):
                period_type = 'fiscalyear'
                if company_fiscalyear_dates.get('record'):
                    string = company_fiscalyear_dates['record'].name
            elif match(*date_utils.get_month(date)):
                period_type = 'month'
            elif match(*date_utils.get_quarter(date)):
                period_type = 'quarter'
            elif match(*date_utils.get_fiscal_year(date)):
                period_type = 'year'
            else:
                period_type = 'custom'

        if not string:
            fy_day = self.env.user.company_id.fiscalyear_last_day
            fy_month = self.env.user.company_id.fiscalyear_last_month
            if self.has_single_date_filter(options):
                string = _('As of %s') % (format_date(self.env, date_to.strftime(DEFAULT_SERVER_DATE_FORMAT)))
            elif period_type == 'year' or (period_type == 'fiscalyear' and (date_from, date_to) == date_utils.get_fiscal_year(date_to)):
                string = date_to.strftime('%Y')
            elif period_type == 'fiscalyear' and (date_from, date_to) == date_utils.get_fiscal_year(date_to, day=fy_day, month=fy_month):
                string = '%s - %s' % (date_to.year - 1, date_to.year)
            elif period_type == 'month':
                string = format_date(self.env, date_to.strftime(DEFAULT_SERVER_DATE_FORMAT), date_format='MMM YYYY')
            elif period_type == 'quarter':
                quarter_names = get_quarter_names('abbreviated', locale=self.env.context.get('lang') or 'en_US')
                string = u'%s\N{NO-BREAK SPACE}%s' % (quarter_names[date_utils.get_quarter_number(date_to)], date_to.year)
            else:
                dt_from_str = format_date(self.env, date_from.strftime(DEFAULT_SERVER_DATE_FORMAT))
                dt_to_str = format_date(self.env, date_to.strftime(DEFAULT_SERVER_DATE_FORMAT))
                string = _('From %s \n to  %s') % (dt_from_str, dt_to_str)
                if options['date'].get('filter', '') == 'today':
                    string = 'Today'

        return {
            'string': string,
            'period_type': period_type,
            'date_from': date_from,
            'date_to': date_to,
        }

    def _apply_date_filter(self, options):
        def create_vals(period_vals):
            vals = {'string': period_vals['string']}
            if self.has_single_date_filter(options):
                vals['date'] = (period_vals['date_to'] or period_vals['date_from']).strftime(DEFAULT_SERVER_DATE_FORMAT)
            else:
                vals['date_from'] = period_vals['date_from'].strftime(DEFAULT_SERVER_DATE_FORMAT)
                vals['date_to'] = period_vals['date_to'].strftime(DEFAULT_SERVER_DATE_FORMAT)
            return vals

        # Date Filter
        if not options.get('date') or not options['date'].get('filter'):
            return
        options_filter = options['date']['filter']

        date_from = None
        date_to = date.today()
        if options_filter == 'custom':
            if self.has_single_date_filter(options):
                date_from = None
                date_to = fields.Date.from_string(options['date']['date'])
            else:
                date_from = fields.Date.from_string(options['date']['date_from'])
                date_to = fields.Date.from_string(options['date']['date_to'])
        elif 'today' in options_filter:
            if not self.has_single_date_filter(options):
                date_from = date.today()
        elif 'month' in options_filter:
            date_from, date_to = date_utils.get_month(date_to)
        elif 'quarter' in options_filter:
            date_from, date_to = date_utils.get_quarter(date_to)
        elif 'year' in options_filter:
            company_fiscalyear_dates = self.env.user.company_id.compute_fiscalyear_dates(date_to)
            date_from = company_fiscalyear_dates['date_from']
            date_to = company_fiscalyear_dates['date_to']
        else:
            raise UserError('Programmatic Error: Unrecognized parameter %s in date filter!' % str(options_filter))

        period_vals = self._get_dates_period(options, date_from, date_to)
        if 'last' in options_filter:
            period_vals = self._get_dates_previous_period(options, period_vals)
        if 'today' in options_filter:
            options['date']['string'] = 'Today'
        options['date'].update(create_vals(period_vals))
        return

    @api.model
    def _get_options(self, previous_options=None):
        if not previous_options:
            previous_options = {}
        options = {}
        filter_list = ['filter_date']
        for element in filter_list:
            filter_name = element[7:]
            options[filter_name] = getattr(self, element)

        for key, value in options.items():
            if key in previous_options and value is not None and previous_options[key] is not None:
                if key == 'date' or key == 'comparison':
                    if key == 'comparison':
                        options[key]['number_period'] = previous_options[key]['number_period']
                    options[key]['filter'] = 'custom'
                    if previous_options[key].get('filter', 'custom') != 'custom':
                        options[key]['filter'] = previous_options[key]['filter']
                    elif value.get('date_from') is not None and not previous_options[key].get('date_from'):
                        date = fields.Date.from_string(previous_options[key]['date'])
                        company_fiscalyear_dates = self.env.user.company_id.compute_fiscalyear_dates(date)
                        options[key]['date_from'] = company_fiscalyear_dates['date_from'].strftime(DEFAULT_SERVER_DATE_FORMAT)
                        options[key]['date_to'] = previous_options[key]['date']
                    elif value.get('date') is not None and not previous_options[key].get('date'):
                        options[key]['date'] = previous_options[key]['date_to']
                    else:
                        options[key] = previous_options[key]
                else:
                    options[key] = previous_options[key]
        return options

    def get_mk_dashboard_informations(self, options):
        '''
        return a dictionary of information that will be needed by the js widget searchview, ...
        '''
        options = self._get_options(options)

        self._apply_date_filter(options)

        searchview_dict = {'options': options, 'context': self.env.context}

        info = {'options': options,
                'context': self.env.context,
                'searchview_html': self.env['ir.ui.view'].render_template('base_marketplace.search_template', values=searchview_dict)}
        return info

    def check_instance_pricelist(self, currency_id):
        if self.pricelist_id:
            instance_currency_id = self.pricelist_id.currency_id
            if instance_currency_id != currency_id:
                raise ValidationError(
                    _("Pricelist's currency and currency get from Marketplace is not same. Marketplace Currency: {}".format(currency_id.name)))
        return True

    def create_pricelist(self, currency_id):
        pricelist_vals = {'name': "{}: {}".format(self.marketplace.title(), self.name),
                          'currency_id': currency_id.id,
                          'company_id': self.company_id.id}
        pricelist_id = self.env['product.pricelist'].create(pricelist_vals)
        return pricelist_id

    def set_pricelist(self, currency_name):
        currency_obj = self.env['res.currency']
        currency_id = currency_obj.search([('name', '=', currency_name)])
        if not currency_id:
            currency_id = currency_obj.search([('name', '=', currency_name), ('active', '=', False)])
            if currency_id:
                currency_id.write({'active': True})
        if not self.check_instance_pricelist(currency_id):
            raise ValidationError(
                _("Set Pricelist currency {} is not match with {} Store Currency {}".format(self.pricelist_id.currency_id.name, self.marketplace.title(), currency_name)))
        if not self.pricelist_id:
            pricelist_id = self.create_pricelist(currency_id)
            if not pricelist_id:
                raise ValidationError(_("Please set pricelist manually with currency: {}".format(currency_id.name)))
            self.pricelist_id = pricelist_id.id
        return True

    def get_fields_for_hide(self):
        marketplace_list = self.env['mk.instance'].get_all_marketplace()
        field_dict = {}
        for marketplace in marketplace_list:
            if hasattr(self, '%s_hide_fields' % marketplace):
                field_list = getattr(self, '%s_hide_fields' % marketplace)()
                field_dict.update({marketplace: field_list})
        return field_dict

    def get_page_for_hide(self):
        marketplace_list = self.env['mk.instance'].get_all_marketplace()
        page_dict = {}
        for marketplace in marketplace_list:
            if hasattr(self, '%s_hide_page' % marketplace):
                page_list = getattr(self, '%s_hide_page' % marketplace)()
                page_dict.update({marketplace: page_list})
        return page_dict

    def get_instance_fields_for_hide(self):
        marketplace_list = self.env['mk.instance'].get_all_marketplace()
        # values = dict((field, getattr(template, field)) for field in fields if getattr(template, field))
        instance_field_dict = {}
        for marketplace in marketplace_list:
            if hasattr(self, '%s_hide_instance_field' % marketplace):
                instance_field_list = getattr(self, '%s_hide_instance_field' % marketplace)()
                instance_field_dict.update({marketplace: instance_field_list})
        return instance_field_dict

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        ret_val = super(MkInstance, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        need_to_hide_field_dict = self.get_fields_for_hide()
        doc = etree.XML(ret_val['arch'])
        if view_type == 'form':
            # For hide page
            need_to_hide_page_list = self.get_page_for_hide()
            for marketplace, instance_field_list in need_to_hide_page_list.items():
                for page in instance_field_list:
                    for node in doc.xpath("//page[@name='%s']" % page):
                        existing_domain, new_domain = [], []
                        if not node.get("modifiers"):
                            node.set("modifiers", json.dumps({'invisible': [('marketplace', '=', marketplace)]}))
                            continue
                        modifiers = json.loads(node.get("modifiers"))
                        if 'invisible' in modifiers and isinstance(modifiers['invisible'], list):
                            if not existing_domain:
                                existing_domain = modifiers['invisible']
                            if not new_domain:
                                new_domain = [('marketplace', '=', marketplace)]
                            else:
                                new_domain = expression.OR([new_domain, [('marketplace', '=', marketplace)]])
                        else:
                            modifiers['invisible'] = [('marketplace', '=', marketplace)]
                        node.set("modifiers", json.dumps(modifiers))
                        if existing_domain and new_domain:
                            node.set("modifiers", json.dumps({'invisible': expression.OR([existing_domain, new_domain])}))
            # For hide instance fields.
            need_to_hide_instance_fields_list = self.get_instance_fields_for_hide()
            for marketplace, instance_field_list in need_to_hide_instance_fields_list.items():
                for instance_field in instance_field_list:
                    for node in doc.xpath("//div[@name='%s']" % instance_field):
                        existing_domain, new_domain = [], []
                        if not node.get("modifiers"):
                            node.set("modifiers", json.dumps({'invisible': [('marketplace', '=', marketplace)]}))
                            continue
                        modifiers = json.loads(node.get("modifiers"))
                        if 'invisible' in modifiers and isinstance(modifiers['invisible'], list):
                            if not existing_domain:
                                existing_domain = modifiers['invisible']
                            if not new_domain:
                                new_domain = [('marketplace', '=', marketplace)]
                            else:
                                new_domain = expression.OR([new_domain, [('marketplace', '=', marketplace)]])
                        else:
                            modifiers['invisible'] = [('marketplace', '=', marketplace)]
                        node.set("modifiers", json.dumps(modifiers))
                        if existing_domain and new_domain:
                            node.set("modifiers", json.dumps({'invisible': expression.OR([existing_domain, new_domain])}))
        for field in ret_val['fields']:
            for node in doc.xpath("//field[@name='%s']" % field):
                existing_domain, new_domain = [], []
                for marketplace, field_list in need_to_hide_field_dict.items():
                    if field in field_list:
                        modifiers = json.loads(node.get("modifiers"))
                        if 'invisible' in modifiers and isinstance(modifiers['invisible'], list):
                            if not existing_domain:
                                existing_domain = modifiers['invisible']
                            if not new_domain:
                                new_domain = [('marketplace', '=', marketplace)]
                            else:
                                new_domain = expression.OR([new_domain, [('marketplace', '=', marketplace)]])
                        else:
                            modifiers['invisible'] = [('marketplace', '=', marketplace)]
                        node.set("modifiers", json.dumps(modifiers))
                if existing_domain and new_domain:
                    node.set("modifiers", json.dumps({'invisible': expression.OR([existing_domain, new_domain])}))
        ret_val['arch'] = etree.tostring(doc, encoding='unicode')
        return ret_val
