# -*- coding: utf-8 -*-

import json
import logging

from odoo import http
from odoo.http import content_disposition, request
from odoo.addons.web.controllers.main import _serialize_exception
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class GetReportController(http.Controller):
    """
    Implement download report API
    """
    @http.route('/get_reports', type='http', auth='user', methods=['POST'], website=False,
                csrf=False)
    def get_report(self, model, options, output_format, token, record_id=None, **kw):
        uid = request.session.uid
        report_obj = request.env[model].sudo(uid)
        options = json.loads(options)
        if record_id and record_id != 'null':
            record_id_int = int(record_id)
            report_obj = report_obj.browse(record_id_int)
            options['record_id'] = record_id_int

        if 'selected_warehouse' in kw:
            options['selected_warehouse'] = kw.get('selected_warehouse', None)
        file_name = options.get('file_name')
        report_name = '%s-%s' % (file_name or report_obj._original_module, report_obj.name_get()[0][1])
        # add report name into `options`
        options.update({
            'report_name': report_name
        })
        _logger.info("Report name: %s", report_name)
        try:
            if output_format == 'xlsx':
                response = request.make_response(
                    None,
                    headers=[
                        ('Content-Type', 'application/vnd.ms-excel'),
                        ('Content-Disposition', content_disposition(report_name + '.xlsx'))
                    ]
                )
                report_obj.get_xlsx(options, response)
            response.set_cookie('fileToken', token)
            return response
        except Exception as e:
            se = _serialize_exception(e)
            error = {
                'code': 400,
                'message': 'Bad Request',
                'data': se
            }
            return request.make_response(html_escape(json.dumps(error)))
