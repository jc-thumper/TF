# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CashflowStructure(models.Model):
    _name = 'cash.flow.report.structure'
    _description = 'Cash Flow Report Structure'

    name = fields.Char('Name')
    line_ids = fields.One2many('cash.flow.report.structure.line', 'structure_id',
                               domain=[('parent_id', '=', False)],
                               string='Report Lines')


class CashflowStructureLine(models.Model):
    _name = 'cash.flow.report.structure.line'
    _description = 'Cash Flow Report Structure Line'

    name = fields.Char('Name')
    sequence = fields.Integer(string='Sequence', default=1)
    level = fields.Integer(string='Level', compute='_compute_level', store=True)
    has_total_line = fields.Boolean('Has Total Line?', default=False,
                                    help='Enable if you want to have a total line in this section.')
    structure_id = fields.Many2one('cash.flow.report.structure', string='Structure', ondelete='restrict')

    account_ids = fields.One2many('account.account', 'cashflow_structure_line_id', string='Accounts in this Section')

    parent_id = fields.Many2one('cash.flow.report.structure.line', string='Parent Line', ondelete='cascade')
    child_ids = fields.One2many('cash.flow.report.structure.line', 'parent_id', string='Sub report lines')

    @api.depends('parent_id', 'parent_id.level')
    def _compute_level(self):
        for record in self:
            if not record.parent_id:
                record.level = 2
            else:
                record.level = record.parent_id.level + 1
