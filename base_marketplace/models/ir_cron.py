from odoo.exceptions import UserError
from odoo import models, fields, api, _
from datetime import datetime
from dateutil.relativedelta import relativedelta


class IrCron(models.Model):
    _inherit = 'ir.cron'

    mk_instance_id = fields.Many2one("mk.instance", string="Marketplace Instance", ondelete='cascade')

    def unlink(self):
        for record in self:
            if record.mk_instance_id:
                raise UserError(_('You can not delete Marketplace Cron because it is associated with Marketplace Instance: {}.'.format(record.mk_instance_id.name)))
        res = super(IrCron, self).unlink()
        return res

    def write(self, vals):
        for record in self:
            if record.mk_instance_id and ('code' in vals or 'model_id' in vals or 'state' in vals):
                raise UserError(_('You can not modify some fields of Marketplace Cron because it is associated with Marketplace Account: {}.'.format(self.mk_instance_id.name)))
        res = super(IrCron, self).write(vals)
        return res

    def create_marketplace_cron(self, mk_instance_id, name, method_name='', model_name='', interval_type='minutes', interval_number=20):
        vals = {'name': name,
                'active': False,
                'numbercall': -1,
                'interval_number': interval_number,
                'interval_type': interval_type,
                'nextcall': fields.Datetime.to_string(datetime.now() + relativedelta(**{interval_type: interval_number})),
                'code': "model.{}({})".format(method_name, mk_instance_id.id),
                'state': 'code',
                'model_id': self.env['ir.model'].search([('model', '=', model_name)]).id,
                'mk_instance_id': mk_instance_id.id,
                'user_id': self.env.user.id}
        self.create(vals)
        return True

    def setup_schedule_actions(self, mk_instance_id):
        """
        Calling hook type method to setup marketplace Crons. Just need to add hook type method in marketplace app.
        :param mk_instance_id: Recordset of mk.instance
        :return: True
        Exp. def shopify_setup_schedule_actions(self, mk_instance_id):
        """
        if hasattr(mk_instance_id, '%s_setup_schedule_actions' % mk_instance_id.marketplace):
            getattr(mk_instance_id, '%s_setup_schedule_actions' % mk_instance_id.marketplace)(mk_instance_id)
        return True
