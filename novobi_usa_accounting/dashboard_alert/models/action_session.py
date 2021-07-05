# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import ast
import logging

import werkzeug.urls

from datetime import datetime, timedelta

from ..utils.utils import random_token
from odoo import api, models, exceptions, fields, _

_logger = logging.getLogger(__name__)


def now(**kwargs):
    return datetime.now() + timedelta(**kwargs)


class ActionSession(models.Model):
    _name = "action.session"
    _description = "The Session of Actions"

    def _token_default_get(self):
        token = random_token()
        while self._action_retrieve(token):
            token = random_token()
        return token

    token = fields.Char('Alert Category', require=True, default=_token_default_get)
    sub_domain = fields.Char(string='Sub domain')
    expiration = fields.Datetime(copy=False, groups="base.group_erp_manager", default=False)
    action_valid = fields.Boolean(compute='_compute_action_valid',
                                  compute_sudo=True,
                                  string="Action's Token is Valid")
    url = fields.Char(compute='_compute_action_url', string="Action's URL")
    item_data = fields.Char(require=True, help='generate json from item._name and item.id')

    _sql_constraints = [
        ('item_data_uniq', 'unique (item_data)', 'You can not have more two session for only one item!'),
    ]

    ########################################################
    # COMPUTED FUNCTION
    ########################################################
    @api.depends('token', 'expiration')
    def _compute_action_valid(self):
        dt = now()
        for action in self:
            action.action_valid = bool(action.token) and \
                                  (not action.expiration or dt <= action.expiration)

    def _compute_action_url(self):
        """ proxy for function field towards actual implementation """
        result = self.sudo()._get_url_for_action()
        for action in self:
            action.url = result.get(action.id, False)

    def action_prepare(self, expiration=False):
        """ Generate a new token for the partners with the given validity, if necessary

            :param expiration: the expiration datetime of the token (string, optional)
        """
        for action in self:
            if expiration or not action.action_valid:
                token = random_token()
                while self._action_retrieve(token):
                    token = random_token()
                action.write({'token': token, 'expiration': expiration})
        return True

    def _action_retrieve(self, token, check_validity=False, raise_exception=False):
        """ find the action corresponding to a token, and possibly check its validity
            :param token: the token to resolve
            :param check_validity: if True, also check validity
            :param raise_exception: if True, raise exception instead of returning False
            :return: partner (browse record) or False (if raise_exception is False)
        """
        action = self.search([('token', '=', token)], limit=1)
        if not action:
            if raise_exception:
                raise exceptions.UserError(_("Action's token '%s' is not valid") % token)
        else:
            if check_validity and not action.action_valid:
                if raise_exception:
                    raise exceptions.UserError(_("Actions token '%s' is no longer valid") % token)
                action = None
        return action

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    @api.model
    def update_new_token(self):
        token = self._token_default_get()
        self.write({
            'token': token
        })
        return token

    def get_corresponding_data(self, token):
        """ Function get corresponding data with data save in action_session table,
        which save token equal with token parameter

        :param token:
            first case: return an corresponding record
            second case: return None value when can not find the record have token equal with
                token parameter
        :return:
        """
        corresponding_obj = None
        action_data = self._action_retrieve(token, check_validity=True, raise_exception=True)
        if action_data:
            object_info_dict = dict(ast.literal_eval(action_data.item_data))
            model_name = object_info_dict['model']
            record_id = object_info_dict['id']
            try:
                corresponding_obj = self.env[model_name] \
                    .with_context(active_test=False) \
                    .search([('id', '=', record_id)])
            except:
                corresponding_obj = None
                _logger.warning("Can not find exactly record have id %s in table %s"
                                % (model_name, record_id,))
        else:
            _logger.warning("Can not find exactly record with token %s" % token)
        return corresponding_obj

    def _get_url_for_action(self):
        """ generate a signup url for the given partner ids and action, possibly overriding
            the url state components (menu_id, id, view_type) """

        res = dict.fromkeys(self.ids, False)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # when required, make sure the action has a valid token
        if self.env.context.get('valid'):
            self.action_prepare()

        for action in self:
            data_item = dict(ast.literal_eval(action.item_data))
            name_func_gen = data_item['func_gen_url']
            record = self.env[data_item['model']].search([('id', '=', data_item['id'])])
            if record:
                if hasattr(record, 'gen_%s_url' % name_func_gen):
                    func = getattr(record, 'gen_%s_url' % name_func_gen, None)
                    url = func(base_url, action.token)
                else:
                    raise NameError(
                        "Do not exist function gen_%s_url in model %r" % (name_func_gen, data_item['model']))
            else:
                model = self.env['ir.model'].search([('model', '=', data_item['model'])])
                if model:
                    raise NameError("Do not exist model %r" % (data_item['model']))
                else:
                    raise NameError("Record having id is %r in model %r was deleted/blocked" %
                                    (data_item['id'], data_item['model']))

            res[action.id] = url
        return res

    def get_item_data(self, item, func_gen_url=None):
        """ Return json is information of record 'item', it is unit

        :param func_gen_url:
        :type item: object
        """
        try:
            item_data = [('model', item._name), ('id', item.id)]
            if func_gen_url:
                item_data.append(('func_gen_url', func_gen_url))
            return str(sorted(item_data))
        except():
            return False

    def get_url(self, func_gen_url, item, num_dates_alive=1):
        """

        :param func_gen_url: Char, name of function generate url
        :param item:
        :param num_dates_alive:
        :return:
        """
        item_data = self.get_item_data(item, func_gen_url)
        if item_data:
            if not isinstance(num_dates_alive, bool):
                expiration = datetime.now() + timedelta(days=num_dates_alive)
            else:
                expiration = False

            session = self.search([('item_data', '=', item_data)])

            if session:
                token = self._token_default_get()
                session.write({
                    'token': token,
                    'expiration': expiration
                })
                self.env.cr.commit()
            else:
                session = self.create({
                    'item_data': item_data,
                    'expiration': expiration
                })
                self.env.cr.commit()
            return session.url
        else:
            return False

    @api.model
    def action_retrieve_info(self, token):
        """ Retrieve the action info about the token
            :return: a dictionary with the user information:
                - 'db': the name of the database
                - 'token': the token, if token is valid
                - 'name': the name of the partner, if token is valid
                - 'login': the user login, if the user already exists
                - 'email': the partner email, if the user does not exist
        """
        action = self._action_retrieve(token, raise_exception=True)
        res = {'db': self.env.cr.dbname}
        if action.action_valid:
            res['token'] = token
            res['sub_domain'] = action.sub_domain
        return res
