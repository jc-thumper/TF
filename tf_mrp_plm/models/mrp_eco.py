from odoo import api, fields, models, _


class MrpEco(models.Model):
    _inherit = 'mrp.eco'

    def action_apply(self):
        super(MrpEco, self).action_apply()

        if self.type in ['bom', 'both']:
            mos = self.env['mrp.production'].search([('bom_id', '=', self.bom_id.id), ('state', '=', 'confirmed')])
            if mos:
                render_context = {
                    'bom': self.bom_id,
                }
                mos.write({'is_changed_bom': True})
                mos.activity_schedule_with_view('mail.mail_activity_data_warning', user_id=mos.user_id.id or self.env.uid,
                                               views_or_xmlid='tf_mrp_plm.exception_change_eco', render_context=render_context)
