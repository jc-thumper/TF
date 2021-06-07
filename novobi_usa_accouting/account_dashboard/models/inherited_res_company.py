# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ..models.usa_journal import BANK
from odoo import models, api, _, fields


class AccountJournal(models.Model):
    _inherit = 'res.company'

    @api.model
    def create(self, value):
        seq = super(AccountJournal, self).create(value)

        usa_journal = self.env['usa.journal']
        type_element = usa_journal.browser('type_element')
        types = [item[0] for item in type_element]
        dict_elem = dict(self.type_element)
        for journal_type in types:
            if journal_type != BANK:
                usa_journal.create({
                    'type': journal_type,
                    'name': dict_elem[journal_type],
                    'code': journal_type.upper(),
                    'company_id': seq.id
                })
        return seq
