# -*- coding: utf-8 -*-

from odoo import _
from odoo.exceptions import UserError


def show_message(curContext, nextContext, name, mes):
    action = curContext.env.ref('account_dashboard.action_view_warning_message').read()[0]
    action['context'] = {
        'content_message': _(mes),
        'next_context': {
            'context': nextContext.env.context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': nextContext._name,
            'res_id': nextContext.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        },
    }
    action['name'] = _(name)
    return action

def show_warning_when_onchange(title, message):
    warning = {
        'title': _(title),
        'message': _(message),
    }
    return {'warning': warning}

def raise_warning_box(message):
    raise UserError(_(message))

def show_popup_warning(self, message):
    action = self.env.ref('account_dashboard.action_view_warning_message').read()[0]
    action['context'] = {
        'content_message': _(message),
    }
    action['name'] = _("Warning")
    return action
