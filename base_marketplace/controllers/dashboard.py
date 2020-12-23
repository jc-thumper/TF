from odoo import http
from odoo.http import request
from datetime import timedelta


class MKDashboard(http.Controller):

    @http.route('/base_marketplace/get_dashboard_data', type="json", auth='user')
    def fetch_dashboard_data(self, mk_instance_id=False, date_from=False, date_to=False):
        if not mk_instance_id:
            mk_instance_id = request.env['mk.instance'].sudo().search([('state', '=', 'confirmed')])
            is_general_dashboard = True
        else:
            is_general_dashboard = False
            mk_instance_id = request.env['mk.instance'].sudo().browse(mk_instance_id)
        dashboard_data = mk_instance_id.get_mk_dashboard_data(date_from, date_to, is_general_dashboard=is_general_dashboard)
        return {'dashboards': dashboard_data}
