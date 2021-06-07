# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2020 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import models, fields, api, _


class Module(models.Model):
    _inherit = 'ir.module.module'
    
    def module_uninstall(self):
        # Unlink all action windows using for viewing audit logs
        for module_to_remove in self:
            if module_to_remove.name == "novobi_audit_trail":
                act_view_log = self.env['ir.actions.act_window'].sudo().search([('res_model', '=', 'audit.trail.log')])
                for act in act_view_log:
                    act.unlink()
        
        return super(Module, self).module_uninstall()
