from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ComponentUsageWizard(models.TransientModel):
    _name = "mrp.component.usage.report.wizard"
    _description = 'Open the popup to allow user choose start date and end date'

    start_date = fields.Datetime(string='Start Date')
    end_date = fields.Datetime(string='End Date')

    def get_report(self):
        self.ensure_one()
        if self.start_date > self.end_date:
            raise UserError(_('End date must be gather than Start Date.'))
        tree_view_id = self.env.ref('tf_stock.mrp_component_usage_report').id
        domain = [('date', '<=', self.end_date), ('date', '>=', self.start_date), ('reference', 'ilike', 'WH/MO')]
        production_location = self.env['stock.location'].search([('name', 'ilike', 'Production')])
        domain += [('location_dest_id', '=', production_location.id)]
        context = {'group_by': ['categ_id', 'product_id'], 'create': False, 'edit': False}
        action = {
            'type': 'ir.actions.act_window',
            'views': [(tree_view_id, 'tree')],
            'view_mode': 'tree',
            'name': _('Component Usage Report (%s - %s)') % (self.start_date, self.end_date),
            'res_model': 'stock.move.line',
            'context': context,
            'domain': domain,
        }

        return action
