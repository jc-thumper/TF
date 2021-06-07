# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import datetime, date, timedelta
from odoo.tools import relativedelta
from odoo.exceptions import ValidationError
from odoo.tools.mimetypes import guess_mimetype
from ..utils.budget_utils import get_last_day_month
import xlrd
from xlrd import xlsx
import base64

FILE_TYPE_DICT = {
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ('xlsx', xlsx, 'xlrd >= 1.0.0'),
}


class AccountBudgetWizard(models.TransientModel):
    _name = "account.budget.wizard"

    name = fields.Char('Name')
    budget_type = fields.Selection([('profit', 'Profit and Loss'), ('balance', 'Balance Sheet')], default='profit')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    action_type = fields.Selection([('create', 'Create New Budget'), ('view', 'View Budget')], default='create')

    _month_range = [(str(x), str(x)) for x in range(1, 13)]
    start_month = fields.Selection(_month_range, string="Start Month", default='1')
    end_month = fields.Selection(_month_range, string="End Month", default='12')

    _this_year = datetime.today().year
    _year_range = [(str(x), str(x)) for x in range(_this_year-1, _this_year+6)]
    start_year = fields.Selection(_year_range, string="Start Year", default=str(_this_year+1))
    end_year = fields.Selection(_year_range, string="End Year", default=str(_this_year+1))

    start_date = fields.Date(compute='_get_start_date', string='Start Date', store=True)
    end_date = fields.Date(compute='_get_end_date', string='End Date', store=True)

    previous_data = fields.Boolean('Previous actual data?', default=False)
    previous_start_date = fields.Date(compute='_get_previous_period', store=True)
    previous_end_date = fields.Date(compute='_get_previous_period', store=True)

    crossovered_budget_id = fields.Many2one('crossovered.budget', 'Budget')
    import_file = fields.Binary('Import File', store=True)

    ############
    # Computed fields
    ############

    @api.depends('start_month', 'start_year', 'action_type', 'crossovered_budget_id')
    def _get_start_date(self):
        for record in self:
            start_date = False
            if record.action_type == 'create':
                if record.start_month and record.start_year:
                    start_date = date(year=int(record.start_year), month=int(record.start_month), day=1)
            else:
                if record.crossovered_budget_id:
                    start_date = record.crossovered_budget_id.date_from

            record.start_date = start_date

    @api.depends('end_month', 'end_year', 'action_type', 'crossovered_budget_id')
    def _get_end_date(self):
        for record in self:
            end_date = False
            if record.action_type == 'create':
                if record.end_month and record.end_year:
                    end_date = get_last_day_month(int(record.end_year), int(record.end_month))
            else:
                if record.crossovered_budget_id:
                    end_date = record.crossovered_budget_id.date_to

            record.end_date = end_date

    @api.depends('start_date', 'end_date', 'previous_data')
    def _get_previous_period(self):
        for record in self:
            previous_start_date = False
            previous_end_date = False

            if record.previous_data:
                previous_start_date = record.start_date - relativedelta(years=1)
                previous_end_date = record.end_date - relativedelta(years=1)

            record.previous_start_date = previous_start_date
            record.previous_end_date = previous_end_date

    @api.onchange('crossovered_budget_id')
    def _onchange_crossovered_budget_id(self):
        if self.crossovered_budget_id:
            self.budget_type = self.crossovered_budget_id.budget_type

    ############
    # Main funcs
    ############
    def view_or_create_form(self):
        name = 'View Budget'
        view_id = self.env.ref('account_budget_advanced.account_budget_view_wizard_form_view').id

        if self.action_type == 'create':
            name = 'Create New Budget'
            view_id = self.env.ref('account_budget_advanced.account_budget_create_wizard_form_view').id
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'account.budget.wizard',
            'target': 'new',
            'res_id': self.id,
        }

    def apply(self):
        name = self.name if self.action_type == 'create' else self.crossovered_budget_id.name

        action_obj = self.sudo().env.ref('account_budget_advanced.action_usa_budget_entry')
        action_obj['params'] = {'budget_wizard_id': self.id}  # for refreshing the page
        action = action_obj.read()[0]
        action.update({
            'name': name,
            'display_name': name,
            'context': {'model': 'usa.budget.entry', 'budget_wizard_id': self.id,
                        'import_data': self.env.context.get('import_data', False)}
        })
        return action

    def import_budget(self):
        decoded_file = base64.b64decode(self.import_file)
        mimetype = guess_mimetype(decoded_file or b'')
        (file_extension, handler, req) = FILE_TYPE_DICT.get(mimetype, (None, None, None))
        error_message = """Sorry! We couldn't import this file.\n
            Please make sure you use the correct template from our export feature."""

        if file_extension != 'xlsx':
            raise ValidationError(_("Sorry, we only support .xlsx file."))

        data = xlrd.open_workbook(file_contents=decoded_file)

        table = data.sheets()[0]
        rows = table.nrows
        import_data = {}

        for i in range(rows):
            data_row = table.row_values(i)
            if data_row[0]:
                if not (isinstance(data_row[0], int) or isinstance(data_row[0], float)):
                    raise ValidationError(_(error_message))
                import_data[int(data_row[0])] = table.row_values(i)

        if not import_data:
            raise ValidationError(_(error_message))

        return self.with_context(import_data=import_data).apply()

    def import_budget_wizard(self):
        self.import_file = False

        view_id = self.env.ref('account_budget_advanced.account_budget_import_wizard_form_view').id

        return {
            'name': 'Import Budget',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'account.budget.wizard',
            'target': 'new',
            'res_id': self.id,
        }

    def close_budget(self):
        return self.env.ref('account.open_account_journal_dashboard_kanban').read()[0]

    def delete_budget(self):
        self.ensure_one()

        if self.crossovered_budget_id:
            self.crossovered_budget_id.unlink()
        return self.close_budget()

    ############
    # Constrains
    ############
    @api.constrains('start_date', 'end_date')
    def _check_date(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_("End Date cannot be earlier than Start Date."))

    @api.constrains('name')
    def _check_name(self):
        budget = self.env['crossovered.budget'].search([('name', '=', self.name)], limit=1)
        if budget:
            raise ValidationError(_("There is already a budget with this name. Please choose a different name."))
