# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2020 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import models, fields, api, _


class AuditTrailLog(models.Model):
    _name = 'audit.trail.log'
    _description = 'Audit Log'
    
    name = fields.Char(string='Name', required=True, copy=False, readonly=True,
                       index=True, default=lambda self: _('New Audit Log'))
    rule_id = fields.Many2one('audit.trail.rule', string='Audit Rule', required=True, ondelete='cascade')
    model_id = fields.Many2one('ir.model', string='Tracking Model', required=True, ondelete='cascade')
    res_id = fields.Integer(string='Resource ID')
    res_name = fields.Char(string='Resource Name')
    res_reference = fields.Char(string='Resource Reference', compute="_compute_reference_and_name")
    res_create_date = fields.Datetime(string='Created Date')
    res_partner_id = fields.Many2one('res.partner', string='Partner')
    res_field_name = fields.Char(string='Changed Field')
    res_old_value = fields.Text(string='Old Value')
    res_new_value = fields.Text(string='New Value')
    author_id = fields.Many2one('res.users', string='User')
    operation = fields.Selection(string='Operation',
                                 selection=[('create', 'Create'), ('read', 'Read'), ('write', 'Edit'),
                                            ('unlink', 'Delete')], required=True)
    create_date = fields.Datetime(string='Date Changed')
    parent_id = fields.Integer(string='Parent ID')
    parent_model_id = fields.Char(string='Parent Model')
    parent_name = fields.Char(string='Parent Name', compute='_compute_reference_and_name')
    parent_reference = fields.Char(string='Parent', compute="_compute_reference_and_name")
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New Audit Log')) == _('New Audit Log'):
            vals['name'] = self.env['ir.sequence'].sudo().next_by_code('audit_trail_log') or _('New Audit Log')
        res = super().create(vals)
        return res
    
    def action_open_all_logs(self):
        self.ensure_one()
        action = self.env.ref('novobi_audit_trail.action_audit_trail_log_tree').read()[0]
        model_id = self.model_id
        rule = self.env['audit.trail.rule'].sudo().search(
            [('model_id', '=', model_id.id), ('state', '=', 'confirmed')], limit=1)
        if rule:
            domain = "['|', '&', ('model_id', '=', {}), ('res_id', '=', {}), '&', ('parent_model_id', '=', '{}'), ('parent_id', '=', {})]".format(
                rule.model_id.id, self.res_id, rule.model_id.model, self.res_id)
        elif model_id:
            domain = [('model_id', '=', model_id.id), ('res_id', '=', self.res_id)]
        else:
            return
        action['domain'] = domain
        return action
    
    @api.depends('res_id', 'model_id', 'parent_id', 'parent_model_id')
    def _compute_reference_and_name(self):
        for log in self:
            # Browse record and parent
            record = None
            parent_record = None
            if log.res_id and log.model_id:
                record = self.env[log.model_id.model].sudo().search([('id', '=', log.res_id)], limit=1)
            if log.parent_id and log.parent_model_id:
                parent_record = self.env[log.parent_model_id].sudo().search([('id', '=', log.parent_id)], limit=1)
            # Check if record and parent is existing
            if record:
                log.res_reference = "%s,%s" % (log.model_id.model, log.res_id)
            else:
                log.res_reference = ''
            if parent_record:
                log.parent_reference = "%s,%s" % (log.parent_model_id, log.parent_id)
                log.parent_name = hasattr(parent_record, 'name') and parent_record.name or parent_record.name_get()[0][
                    1]
            else:
                log.parent_reference = ''
                log.parent_name = ''
