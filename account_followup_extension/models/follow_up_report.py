# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountFollowupReport(models.AbstractModel):
    _inherit = "account.followup.report"

    def _get_columns_name(self, options):
        headers = super()._get_columns_name(options)
        headers[4] = {'name': 'Reference', 'style': 'text-align:right; white-space:nowrap;'}
        return headers

    def _get_lines(self, options, line_id=None):
        lines = super()._get_lines(options, line_id)
        for line in lines:
            inv_number = line['name']
            communication = line['columns'][3]['name']
            line['columns'][3]['name'] = communication.replace('%s-' % inv_number, '')
        return lines

    def _get_report_name(self):
        return "Account Statement"


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
