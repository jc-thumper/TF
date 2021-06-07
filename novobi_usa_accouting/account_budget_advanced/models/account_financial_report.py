# -*- coding: utf-8 -*-


from odoo import models, api, _, fields


class ReportLine(models.Model):
    _inherit = 'account.financial.html.report.line'

    hide_in_budget = fields.Boolean('Hide in Budget',
                                    help='Set to True to hide this section in budget planning & report.')

