from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductionWizard(models.TransientModel):
    _name = "mrp.production.report.wizard"
    _description = 'Open the popup to allow user choose start date and end date'

    start_date = fields.Datetime(string='Start Date', default=fields.Datetime.now())
    end_date = fields.Datetime(string='End Date', default=fields.Datetime.now())

    @api.onchange('start_date', 'end_date')
    def _onchange_start_end_date(self):
        self.ensure_one()
        if self.start_date > self.end_date:
            raise UserError(_('End date must be gather than Start Date.'))

    def get_report(self):
        self.ensure_one()
        tree_view_id = self.env.ref('tf_stock.production_report').id
        domain = [('date', '<=', self.end_date), ('date', '>=', self.start_date)]
        domain += [('reference', 'ilike', 'WH/MO')]
        production_location = self.env['stock.location'].search([('name', 'ilike', 'Production')])
        domain += [('location_id', '=', production_location.id)]
        context = {'group_by': ['categ_id', 'product_id']}
        action = {
            'type': 'ir.actions.act_window',
            'views': [(tree_view_id, 'tree')],
            'view_mode': 'tree',
            'name': _('Production Report ({} - {})').format(self.start_date, self.end_date),
            'res_model': 'stock.move.line',
            'context': context,
            'domain': domain,
        }

        return action
