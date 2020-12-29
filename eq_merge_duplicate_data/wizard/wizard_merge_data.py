# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2019 EquickERP
#
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

SKIP_MODEL = ['_unknown', 'base', 'base_import.mapping', 'base_import.tests.models.char',
              'base_import.tests.models.char.noreadonly', 'base_import.tests.models.char.readonly',
              'base_import.tests.models.char.required', 'base_import.tests.models.char.states',
              'base_import.tests.models.char.stillreadonly', 'base_import.tests.models.complex',
              'base_import.tests.models.float', 'base_import.tests.models.m2o', 'base_import.tests.models.m2o.related',
              'base_import.tests.models.m2o.required', 'base_import.tests.models.m2o.required.related',
              'base_import.tests.models.o2m', 'base_import.tests.models.o2m.child', 'base_import.tests.models.preview',
              'format.address.mixin', 'ir.actions.act_url', 'ir.actions.act_window', 'ir.actions.act_window.view',
              'ir.actions.act_window_close', 'ir.actions.actions', 'ir.actions.client', 'ir.actions.report',
              'ir.actions.server', 'ir.actions.todo', 'ir.attachment', 'ir.autovacuum', 'ir.config_parameter',
              'ir.cron', 'ir.default', 'ir.exports', 'ir.exports.line', 'ir.fields.converter', 'ir.filters',
              'ir.http', 'ir.logging', 'ir.mail_server', 'ir.model', 'ir.model.access', 'ir.model.constraint',
              'ir.model.data', 'ir.model.fields', 'ir.model.relation', 'ir.module.category', 'ir.module.module',
              'ir.module.module.dependency', 'ir.module.module.exclusion', 'ir.property', 'ir.qweb', 'ir.qweb.field',
              'ir.qweb.field.barcode', 'ir.qweb.field.contact', 'ir.qweb.field.date', 'ir.qweb.field.datetime',
              'ir.qweb.field.duration', 'ir.qweb.field.float', 'ir.qweb.field.float_time', 'ir.qweb.field.html',
              'ir.qweb.field.image', 'ir.qweb.field.integer', 'ir.qweb.field.many2many', 'ir.qweb.field.many2one',
              'ir.qweb.field.monetary', 'ir.qweb.field.qweb', 'ir.qweb.field.relative', 'ir.qweb.field.selection',
              'ir.qweb.field.text', 'ir.rule', 'ir.sequence.date_range', 'ir.server.object.lines', 'ir.translation',
              'ir.ui.menu', 'ir.ui.view', 'ir.ui.view.custom', 'report.base.report_irmodulereference', 'report.layout',
              'web_editor.converter.test', 'web_editor.converter.test.sub', 'web_tour.tour', 'mail.tracking.value', 'mail.mail',
              'mail.message', 'res.users.log', 'iap.account', 'wizard.merge.data']


class WizardMergeData(models.Model):
    _name = 'wizard.merge.data'
    _description = "Merge Data"

    @api.model
    def fetch_model_list(self):
        model_lst = []
        for model in self.env['ir.model'].search([('transient', '=', False)], order='name'):
            if model.model in SKIP_MODEL:
                continue
            model_lst += [(model.model, model.name + " (%s)" % (model.model))]
        return model_lst

    duplicate_rec_id = fields.Reference(selection='fetch_model_list', string="Duplicate Record")
    original_rec_id = fields.Reference(selection='fetch_model_list', string="Original Record")
    take_action = fields.Selection([('none', 'None'),
                                    ('delete', 'Delete'),
                                    ('archived', 'Archived')],
                                   default="delete",
                                   string="Action on Duplicate Record",
                                   help="""If this option is not selected, then the duplicate record will remains into database as it is. Only update the reference of the duplicate record.
                                        * Delete : it means the duplicate record will be delete.
                                        * Archived : it means it will exist into database as archived record. For this action into the table must be have 'active' field.""")

    def action_merge_duplicate_data(self):
        duplicate_id = self.duplicate_rec_id
        original_id = self.original_rec_id
        if duplicate_id._name != original_id._name:
            raise ValidationError(_('Please select same Models.'))
        if duplicate_id.id == original_id.id:
            raise ValidationError(_('Please select different Record ID.'))
        self._cr.execute('''SELECT tc.constraint_name "constraint_name",
                                   tc.table_name "FK_tbl_name",
                                   kcu.column_name "FK_col_name",
                                   ccu.table_name "PK_tbl_name",
                                   ccu.column_name "PK_col_name"
                            FROM information_schema.table_constraints tc
                                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                                JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
                            WHERE constraint_type = 'FOREIGN KEY'
                                AND ccu.table_name='%s' ''' % duplicate_id._table)
        used_ref_table_list = self._cr.dictfetchall()

        list_of_fields = self.env['ir.model.fields'].sudo().search([('model', '=', original_id._name),
                                                                    ('ttype', '=', 'many2one'),
                                                                    ('relation', '=', original_id._name)]).mapped('name')
        # for checking the parent-child relation ship
        if original_id._parent_name in list_of_fields:
            qry_dict = {'table': original_id._table,
                        'parent_col': original_id._parent_name,
                        'original_id': original_id.id}
            qry = """WITH RECURSIVE result_table AS (
                        SELECT id, %(parent_col)s FROM %(table)s WHERE id = %(original_id)s
                        UNION ALL
                        SELECT sub.id, sub.%(parent_col)s FROM %(table)s sub
                            INNER JOIN result_table r ON sub.id=r.%(parent_col)s
                    )
                    SELECT %(parent_col)s FROM result_table""" % qry_dict
            self._cr.execute(qry)
            check_parent_rec_qry_result = list(filter(None, map(lambda x: x[0], self._cr.fetchall())))
            if duplicate_id.id in check_parent_rec_qry_result:
                raise ValidationError(_("You cannot merge a record with parent record."))
        # Update reference into table.
        for each in used_ref_table_list:
            fk_table = each.get('FK_tbl_name')
            fk_col = each.get('FK_col_name')
            # Get column of all Table
            result = self._cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = '%s'" % (fk_table))
            other_column = []
            for data in self._cr.fetchall():
                if data[0] != fk_col:
                    other_column.append(data[0])
            params = {
                'table': fk_table,
                'column': fk_col,
                'value': other_column[0],
                'duplicate_id': duplicate_id.id,
                'original_id': original_id.id
            }
            if len(other_column) <= 1:
                self._cr.execute("""
                    UPDATE "%(table)s" as main1
                    SET "%(column)s" = %(original_id)s
                    WHERE
                        "%(column)s" = %(duplicate_id)s AND
                        NOT EXISTS (
                            SELECT 1
                            FROM "%(table)s" as sub1
                            WHERE
                                "%(column)s" = %(original_id)s AND
                                main1.%(value)s = sub1.%(value)s
                        )""" % params)
            else:
                try:
                    with mute_logger('odoo.sql_db'), self._cr.savepoint():
                        qry = '''UPDATE %(table)s SET %(column)s = %(original_id)s
                                    WHERE %(column)s = %(duplicate_id)s''' % params
                        self._cr.execute(qry)
                except Exception as e:
                    raise ValidationError(_('Error %s') % e)
        for fieldname in original_id._field_computed.keys():
            fieldname.compute_value(original_id)
            fieldname.compute_value(duplicate_id)
        
        # UPDATE The display_name value
        if 'name' in original_id._fields:
            old_name = original_id.sudo().name
            original_id.sudo().write({'name': old_name})
        
        # Update the parent_path into parent-child relation table like product category, location
        original_id._parent_store_compute()
        
        # Action on the the duplicate records
        if self.take_action == 'delete':
            self._cr.execute(""" DELETE FROM %s WHERE id = %s """ % (duplicate_id._table, duplicate_id.id))
        if self.take_action == 'archived':
            if 'active' in self.duplicate_rec_id.fields_get():
                self._cr.execute("""UPDATE %s SET active='f' WHERE id=%s""" % (duplicate_id._table, duplicate_id.id))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: