# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class MailFollowers(models.Model):
    _inherit = "mail.followers"

    def _add_followers(self, res_model, res_ids, partner_ids, partner_subtypes, channel_ids, channel_subtypes, check_existing=False, existing_policy='skip'):
        if self._context.get('apply_mode', '') != 'direct':
            users = self.env['res.users'].search([('partner_id', 'in', partner_ids)]).filtered(lambda rec: rec.has_group('base.group_user'))
            partner_ids = users.mapped('partner_id').ids or []

        return super(MailFollowers, self)._add_followers(res_model, res_ids, partner_ids, partner_subtypes, channel_ids, channel_subtypes, check_existing, existing_policy)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
