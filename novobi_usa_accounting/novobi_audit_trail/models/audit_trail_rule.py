# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2020 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import models, fields, api, _, modules

DEFAULT_OPERATIONS = ['create', 'write', 'unlink']


class AuditTrailRule(models.Model):
    _name = 'audit.trail.rule'
    _description = 'Audit Rule'
    
    name = fields.Char(string='Name', required=True, default='New Audit Rule')
    model_id = fields.Many2one('ir.model', string='Tracking Model', required=True, ondelete='cascade')
    is_track_create = fields.Boolean(string='Track Create Operation', default=True)
    is_track_write = fields.Boolean(string='Track Edit Operation', default=True)
    is_track_unlink = fields.Boolean(string='Track Delete Operation', default=True)
    state = fields.Selection(string='Status',
                             selection=[('draft', 'Draft'), ('confirmed', 'Confirmed'), ('cancel', 'Cancelled')],
                             required=True, default='draft')
    tracking_field_ids = fields.Many2many('ir.model.fields', string='Tracking Fields')
    is_tracking_all_fields = fields.Boolean("Track All Fields", default=True)
    parent_field_id = fields.Many2one('ir.model.fields', string='Parent Field')
    
    _sql_constraints = [
        ('unique_rule_per_model', 'unique(model_id)', "A tracking model must have only one tracking rule.")]
    
    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.tracking_field_ids.unlink()
    
    def action_confirm_rule(self):
        """
        Set state to `Confirmed` after users click on `Confirm` button
        :return:
        """
        self.update({'state': 'confirmed'})
        self._register_hook()
    
    def action_cancel_rule(self):
        """
        Set state to `Cancelled` after users click on `Cancel` button
        :return:
        """
        self.update({'state': 'cancel'})
    
    def action_set_draft(self):
        """
        Set state to `Draft` after users click on `Set To Draft` button
        :return:
        """
        self.update({'state': 'draft'})
    
    def _register_hook(self):
        """
        Register hook for tracking changes
        :return: TRUE if the model already registered hook, else FALSE
        """
        res = super()._register_hook()
        if not self:
            self = self.env['audit.trail.rule'].search([('state', '=', 'confirmed')])
        return self._is_need_to_patch_default_methods() or res
    
    def _is_need_to_patch_default_methods(self):
        """
        Monkey-patch the default CREATE/WRITE/DELETE methods (if needed) for tracking changes when calling to these methods
        :return: TRUE if it needs to patch at least one of these above default methods, else FALSE
        """
        confirmed_rules = self.filtered(lambda r: r.state == 'confirmed')
        is_patch_default_method = False
        for rule in confirmed_rules:
            tracking_model = self.env[rule.model_id.model].sudo()
            
            for field in ['is_track_create', 'is_track_write', 'is_track_unlink']:
                if getattr(rule, field, False) and not hasattr(tracking_model, field + '_created'):
                    tracking_method = field[field.rfind('_') + 1:]
                    rule.sudo()._monkey_patch_method(tracking_model, tracking_method)
                    setattr(type(tracking_model), field + '_created', True)
                    is_patch_default_method = True
            act_view_log = self.env['ir.actions.act_window'].sudo().search(
                [('res_model', '=', 'audit.trail.log'), ('binding_model_id', '=', rule.model_id.id)])
            if not act_view_log:
                rule.create_action_view_audit_log()
        return is_patch_default_method
    
    def _monkey_patch_method(self, tracking_model, method_name):
        """
        Monkey-patch the default CREATE/WRITE/DELETE methods (if needed) for tracking changes when calling to these methods
        :param tracking_model: model object
        :param method_name: name of method
        :return:
        """
        
        @api.model
        def tracking_create_operation(self, vals):
            res = tracking_create_operation.origin(self, vals)
            if isinstance(vals, list):
                keys_list = [list(vals_i.keys()) for vals_i in vals]
            elif isinstance(vals, dict):
                keys_list = [list(vals.keys())]
            else:
                keys_list = []
            new_values = self.env['audit.trail.rule'].sudo().get_tracking_value(res, keys_list)
            self.env['audit.trail.rule'].sudo().create_audit_trail_log('create', res, new_values=new_values)
            return res
        
        def tracking_write_operation(self, vals):
            if isinstance(vals, list):
                keys_list = [list(vals_i.keys()) for vals_i in vals]
            elif isinstance(vals, dict):
                keys_list = [list(vals.keys())]
            else:
                keys_list = []
            old_values = self.env['audit.trail.rule'].sudo().get_tracking_value(self, keys_list)
            res = tracking_write_operation.origin(self, vals)
            new_values = self.env['audit.trail.rule'].sudo().get_tracking_value(self, keys_list)
            self.env['audit.trail.rule'].sudo().create_audit_trail_log('write', self, old_values,
                                                                                   new_values)
            return res
        
        def tracking_unlink_operation(self):
            self.env['audit.trail.rule'].sudo().create_audit_trail_log('unlink', self)
            res = tracking_unlink_operation.origin(self)
            return res
        
        def tracking_modify_operation(self, vals):
            computed_fields = [field.name for field in self._field_computed]
            if isinstance(vals, list):
                keys_list = [[key for key in list(vals_i.keys()) if key in computed_fields] for vals_i in vals]
            elif isinstance(vals, dict):
                keys_list = [[key for key in list(vals.keys()) if key in computed_fields]]
            else:
                keys_list = []
            old_values = self.env['audit.trail.rule'].sudo().query_field_from_db(self)
            res = tracking_modify_operation.origin(self, vals)
            new_values = self.env['audit.trail.rule'].sudo().get_tracking_value(self, keys_list)
            self.env['audit.trail.rule'].sudo().create_audit_trail_log('write', self, old_values,
                                                                                   new_values)
            return res
        
        tracking_function = False
        if method_name == 'create':
            tracking_function = tracking_create_operation
        elif method_name == 'write':
            tracking_function = tracking_write_operation
            tracking_model._patch_method('_write', tracking_modify_operation)
            setattr(type(tracking_model), 'is_track_modify_created', True)
        elif method_name == 'unlink':
            tracking_function = tracking_unlink_operation
        if tracking_function:
            tracking_model._patch_method(method_name, tracking_function)
    
    def remove_all_patch_methods(self, operation_list=DEFAULT_OPERATIONS, is_delete=False):
        """
        Remove all patched methods (create/write/unlink) to origin
        :return:
        """
        is_need_to_reset = False
        binding_model_ids = []
        for rule in self:
            binding_model_ids.append(rule.model_id.id)
            tracking_model = self.env[rule.model_id.model].sudo()
            for operation in operation_list:
                if getattr(rule, 'is_track_{}'.format(operation)) and hasattr(getattr(tracking_model, operation),
                                                                              'origin') and \
                        getattr(tracking_model, 'is_track_{}_created'.format(operation), False):
                    tracking_model._revert_method(operation)
                    delattr(type(tracking_model), 'is_track_{}_created'.format(operation))
                    is_need_to_reset = True
                if operation == 'write':
                    if hasattr(getattr(tracking_model, '_write'), 'origin') and \
                            getattr(tracking_model, 'is_track_modify_created', False):
                        tracking_model._revert_method('_write')
                        delattr(type(tracking_model), 'is_track_modify_created')
                        is_need_to_reset = True
        if is_delete:
            act_view_log = self.env['ir.actions.act_window'].sudo().search(
                [('res_model', '=', 'audit.trail.log'), ('binding_model_id', 'in', binding_model_ids)])
            for act in act_view_log:
                act.unlink()
        if is_need_to_reset:
            modules.registry.Registry(self.env.cr.dbname).signal_changes()
    
    @api.model
    def create_audit_trail_log(self, operation, records, old_values={}, new_values={}):
        """
        Create a log to record the changes with the operation create/write/unlink
        :param operation: create/write/unlink
        :param records: the resource records
        :param old_values: the old values
        :param new_values: the new values
        :return: created log for recording the changes
        """
        created_log = []
        for record in records:
            record = record.sudo()
            # Create log
            rule = new_values.get(record.id) and new_values[record.id].get('rule')
            res_string_fields = self.env['ir.translation'].sudo().get_field_string(record._name)
            res_partner_id = getattr(record, 'partner_id', '')
            audit_log_env = self.env['audit.trail.log'].sudo()
            has_parent_id = rule and hasattr(rule, 'parent_field_id') and rule.parent_field_id
            record_name = hasattr(record, 'name') and record.name or record.name_get()[0][1]
            if operation == 'unlink':
                model_id = self.env['ir.model'].sudo().search([('model', '=', record._name)], limit=1)
                tracking_rule = self.env['audit.trail.rule'].sudo().search(
                    [('model_id', '=', model_id.id), ('state', '=', 'confirmed')], limit=1)
                
                log_vals = {
                    'rule_id': tracking_rule and tracking_rule.id,
                    'res_name': record_name,
                    'parent_id': has_parent_id and getattr(record, rule.parent_field_id.name).id or False,
                    'parent_model_id': has_parent_id and getattr(record, rule.parent_field_id.name)._name or False,
                    'res_create_date': getattr(record, 'create_date', None),
                    'res_partner_id': res_partner_id and res_partner_id.id,
                    'model_id': self.env['ir.model'].sudo().search([('model', '=', record._name)], limit=1).id,
                    'res_id': record.id,
                    'author_id': self.env.user.id,
                    'operation': operation,
                }
                log = audit_log_env.create(log_vals)
                created_log.append(log)
            else:
                # Track changes
                record_old_values = old_values.get(record.id, {}) and old_values[record.id].get('values', [])
                record_new_values = new_values.get(record.id, {}) and new_values[record.id].get('values', [])
                untracking_fields = ['message_ids', '__last_update', 'message_follower_ids', 'write_date']
                for key in record_new_values.keys():
                    old_value = record_old_values.get(key, '')
                    new_value = record_new_values.get(key, '')
                    if old_value != new_value and (old_value or new_value) and key not in untracking_fields:
                        # Create log if the change occurs
                        log_vals = {
                            'rule_id': rule and rule.id,
                            'res_name': record_name,
                            'parent_id': has_parent_id and getattr(record, rule.parent_field_id.name).id or False,
                            'parent_model_id': has_parent_id and getattr(record,
                                                                         rule.parent_field_id.name)._name or False,
                            'res_create_date': getattr(record, 'create_date', None),
                            'res_partner_id': res_partner_id and res_partner_id.id,
                            'res_field_name': res_string_fields.get(key, ''),
                            'res_old_value': old_value,
                            'res_new_value': new_value,
                            'model_id': self.env['ir.model'].sudo().search([('model', '=', record._name)], limit=1).id,
                            'res_id': record.id,
                            'author_id': self.env.user.id,
                            'operation': operation,
                        }
                        log = audit_log_env.create(log_vals)
                        created_log.append(log)
        return created_log
    
    @api.model
    def get_tracking_value(self, records, keys_list):
        """
        Get current value of specific fields in the `keys` list
        :param records: records that need to get the value
        :param keys_list: list of the fields names of each record
        :return: dictionary of values
        """
        tracking_dict = {}
        length = len(records)
        keys_list = length == len(keys_list) and keys_list or [keys_list[0] for record in records]
        model_id = self.env['ir.model'].sudo().search([('model', '=', records._name)], limit=1)
        tracking_rule = self.env['audit.trail.rule'].sudo().search(
            [('model_id', '=', model_id.id), ('state', '=', 'confirmed')], limit=1)
        if tracking_rule:
            if tracking_rule.is_tracking_all_fields:
                tracking_fields = self.env['ir.model.fields'].sudo().search(
                    [('model', '=', records._name), ('store', '=', True)])
            else:
                tracking_fields = tracking_rule.tracking_field_ids
            for i in range(0, length):
                record = records[i].sudo()
                keys_list_i = keys_list[0]
                value_dict = {}
                for key in keys_list_i:
                    changed_fields = tracking_fields.filtered(lambda f: f.name == key)
                    changed_field = len(changed_fields) > 1 and changed_fields[0] or changed_fields
                    if changed_field:
                        if changed_field['relation']:
                            value = record[key].name_get()
                            value_dict[key] = '\n'.join([name and name[1] for name in value])
                        elif changed_field['ttype'] == 'selection':
                            selection = self.env[record._name].sudo()._fields[key].selection
                            value_dict[key] = isinstance(selection, list) and dict(selection).get(record[key]) or ''
                        else:
                            value_dict[key] = record[key]
                tracking_dict[record.id] = {
                    'values': value_dict,
                    'rule': tracking_rule,
                    'model': model_id,
                }
        return tracking_dict
    
    @api.model
    def query_field_from_db(self, records):
        tracking_dict = {}
        if records:
            in_table_list = ['id']
            one2many_list = []
            many2many_list = []
            model_id = self.env['ir.model'].sudo().search([('model', '=', records._name)], limit=1)
            tracking_rule = self.env['audit.trail.rule'].sudo().search(
                [('model_id', '=', model_id.id), ('state', '=', 'confirmed')], limit=1)
            if tracking_rule:
                if tracking_rule.is_tracking_all_fields:
                    tracking_fields = self.env['ir.model.fields'].sudo().search(
                        [('model', '=', records._name), ('store', '=', True)])
                else:
                    tracking_fields = tracking_rule.tracking_field_ids
                fields = tracking_fields.filtered(lambda f: f['ttype'] != 'binary')
                for field in fields:
                    if field['relation']:
                        if 'one2many' in field['ttype']:
                            one2many_list.append(field)
                        elif 'many2many' in field['ttype']:
                            many2many_list.append(field)
                        else:
                            in_table_list.append(field.name)
                    else:
                        in_table_list.append(field.name)
                
                query_stmt = """
                    SELECT {}
                    FROM {}
                    WHERE id IN ({})
                """.format(','.join(in_table_list), records._table,
                           ','.join(str(record.id) for record in records))
                cr = self.env.cr
                cr.execute(query_stmt)
                result = {line['id']: line for line in cr.dictfetchall()}
                
                for record in records:
                    # Query many2many fields
                    for field in many2many_list:
                        relation_table = field.relation_table
                        column_name = field.column1
                        ref_column_name = field.column2
                        query_stmt = """
                                            SELECT {}
                                            FROM {}
                                            WHERE {} = {}
                                        """.format(ref_column_name, relation_table, column_name, record.id)
                        cr.execute(query_stmt)
                        field_result = cr.dictfetchall()
                        result[record.id][field.name] = [value[ref_column_name] for value in field_result]
                    # Query one2many fields
                    for field in one2many_list:
                        if field.relation_field:
                            column_name = field.relation_field
                            relation_table = field.relation.replace('.', '_')
                            query_stmt = """
                                SELECT id
                                FROM {}
                                WHERE {} = {}
                            """.format(relation_table, column_name, record.id)
                            cr.execute(query_stmt)
                            field_result = cr.dictfetchall()
                            result[record.id][field.name] = [value['id'] for value in field_result]
                    
                    value_dict = {}
                    old_value_dict = result.get(record.id)
                    if old_value_dict:
                        for field in fields:
                            if field['relation']:
                                relation_record = self.env[field.relation].sudo().browse(old_value_dict[field.name])
                                value = relation_record.name_get()
                                value_dict[field.name] = '\n'.join([name and name[1] for name in value])
                            elif field['ttype'] == 'selection':
                                selection = self.env[record._name].sudo()._fields[field.name].selection
                                value_dict[field.name] = isinstance(selection, list) and dict(selection).get(
                                    old_value_dict[field.name]) or ''
                            elif not field['relation']:
                                value_dict[field.name] = old_value_dict[field.name]
                    tracking_dict[record.id] = {
                        'values': value_dict,
                        'rule': tracking_rule,
                        'model': model_id,
                    }
        return tracking_dict
    
    def create_action_view_audit_log(self):
        """
        Create new action item in the form view for tracking model to view the audit logs
        :return:
        """
        obj_env = self.env['ir.actions.act_window'].sudo()
        for rule in self:
            domain = "['|', '&', ('model_id', '=', {}), ('res_id', 'in', active_ids), '&', ('parent_model_id', '=', '{}'), ('parent_id', 'in', active_ids)]".format(
                rule.model_id.id, rule.model_id.model)
            vals = {
                'name': _('Audit Logs'),
                'res_model': 'audit.trail.log',
                'binding_model_id': rule.model_id.id,
                'binding_view_types': 'form',
                'view_mode': 'list,form',
                'domain': domain,
            }
            obj_env.create(vals)
    
    def write(self, vals):
        # Remove tracking operations after user disable it
        operations = DEFAULT_OPERATIONS
        self.remove_all_patch_methods(operation_list=operations)
        res = super().write(vals)
        # Register hook for tracking operations
        self._register_hook()
        return res
    
    def unlink(self):
        # Remove all patched methods to resource models before unlink the rules
        self.remove_all_patch_methods(is_delete=True)
        return super().unlink()
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New Audit Rule')) == _('New Audit Rule'):
            vals['name'] = self.env['ir.sequence'].sudo().next_by_code('audit_trail_rule') or _('New Audit Rule')
        res = super().create(vals)
        return res
