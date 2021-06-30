# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.http import request

from odoo.addons.si_core.utils.request_utils import check_format_data_array, check_request_authentication, \
    handle_push_data_request

_logger = logging.getLogger(__name__)


class ReorderingRuleWithForecastAPI(http.Controller):
    """
    Implement APIs to receive the reordering rules from the FE server
    """

    @http.route('/api/update_rrwf_result', type='json', auth="none", methods=['POST'],
                website=False, csrf=False)
    def update_rrwf_result(self, **kwargs):
        """
        Update the table Reordering Rules with Forecast with the new result
        request: {
                    "server_pass": "0e3551a9-8de6-4429-aa19-3db56bc3995c",
                     "data": [
                        {
                            'min_forecast': record.min_forecast,
                            'max_forecast': record.max_forecast,
                            'eoq': record.eoq,
                            'create_time': record.create_time,
                            'pub_time': record.pub_time
                        },..
                    ]
                }
        :param kwargs:
        :return:
        """
        _logger.info('Reordering Rules with Forecast result.', extra={})
        response_message = handle_push_data_request(request=request,
                                                    model=request.env['reordering.rules.with.forecast.tracker'])
        return response_message
