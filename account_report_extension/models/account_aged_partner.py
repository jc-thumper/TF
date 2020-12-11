# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ReportAccountAgedReceivable(models.AbstractModel):
    _inherit = "account.aged.receivable"

    def _get_columns_name(self, options):
        columns = super(ReportAccountAgedReceivable, self)._get_columns_name(options)
        columns.insert(1, {'name': _("Customer Reference"), 'class': '', 'style': 'text-align:center; white-space:nowrap;'})
        return columns


class ReportAccountAgedPayable(models.AbstractModel):
    _inherit = "account.aged.payable"

    def _get_columns_name(self, options):
        columns = super(ReportAccountAgedPayable, self)._get_columns_name(options)
        columns.insert(1, {'name': _("Bill Reference"), 'class': '', 'style': 'text-align:center; white-space:nowrap;'})
        return columns


class ReportAccountAgedPartner(models.AbstractModel):
    _inherit = "account.aged.partner"

    @api.model
    def _get_lines(self, options, line_id=None):
        AccountMoveLine = self.env['account.move.line'].sudo()

        lines = super(ReportAccountAgedPartner, self)._get_lines(options, line_id)

        for line in lines:
            if line['level'] == 2:
                line['columns'].insert(1, {'name': ''})
            elif line['level'] == 4:
                aml = AccountMoveLine.browse(line['id'])
                line['columns'].insert(0, {'name': aml.move_id.ref or ''})

        return lines


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
