# -*- coding: utf-8 -*-

from odoo import api, fields, models

from odoo.exceptions import AccessError


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def open_tablet_view(self):
        self.ensure_one()
        if self._uid not in self.workcenter_id.user_ids.ids and not self.env.user.has_group('mrp.group_mrp_manager'):
            raise AccessError("You are not allowed to Process this Workorder")

        return super(MrpWorkorder, self).open_tablet_view()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
