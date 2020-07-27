# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class Shipstation(http.Controller):

    @http.route('/shipstation/get_dashboard_data', type="json", auth='user')
    def fetch_shipstation_data(self):
        results = {}
        dashboard_data = dict(carrier_count=0)
        carrier = request.env['shipstation.carrier'].search([])
        dashboard_data['carrier_count'] = len(carrier)
        return dashboard_data

    @http.route('''/shipstation/webhook/notification/<int:account>''', type='json', auth="public")
    def shipstation_webhook_notification(self, account=None, **kwargs):
        data = request.jsonrequest and request.jsonrequest or {}
        order_obj = request.env['sale.order'].sudo()
        if data.get('resource_type') == 'ORDER_NOTIFY':
            order_obj.import_order_from_webhook_notification(data.get('resource_url'), account)
            return 'SUCCESS'
        return 'FAILURE'
