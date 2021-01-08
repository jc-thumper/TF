# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class MailFollowers(models.Model):
    _inherit = "mail.followers"

    def _add_followers(self, res_model, res_ids, partner_ids, partner_subtypes, channel_ids, channel_subtypes, check_existing=False, existing_policy='skip'):
        if self._context.get('apply_mode', '') != 'direct':
            users = self.env['res.users'].search([('partner_id', 'in', partner_ids), ('active', 'in', [True, False])])
            partner_ids = users.filtered(lambda rec: rec.user_has_groups('base.group_user,base.group_public')).mapped('partner_id').ids or []

        return super(MailFollowers, self)._add_followers(res_model, res_ids, partner_ids, partner_subtypes, channel_ids, channel_subtypes, check_existing, existing_policy)


# The internal user will be added as a follower when tagged in the Note section.

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        return super(ProductTemplate, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        return super(ProductProduct, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        return super(ResPartner, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        return super(MrpProduction, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        return super(MrpWorkorder, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)


class MrpEco(models.Model):
    _inherit = 'mrp.eco'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        return super(MrpEco, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        return super(AccountMove, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
