# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import logging

from odoo import api, models, fields, modules, tools, _

_logger = logging.getLogger(__name__)


class InheritedResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _default_channel_rec_mes_ids(self):
        default_channel_ids = self.env['alert.channel'].search([('channel_default', '=', True)]).ids
        return [(6, 0, default_channel_ids)]

    channel_rec_mes_ids = fields.Many2many('alert.channel',
                                           'res_partner_alert_channel_rel',
                                           'partner_id', 'channel_id',
                                           default=_default_channel_rec_mes_ids, string='Alert Channel')

    ########################################################
    # BUTTON EVENT
    ########################################################
    def preference_save(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_context',
        }
