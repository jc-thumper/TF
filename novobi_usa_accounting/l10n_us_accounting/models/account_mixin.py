# -*- coding: utf-8 -*-
from ..models.model_const import IR_MODEL_DATA


class AccountMixinUSA(object):

    def redirect_to_edit_mode_form(self, form_view, res_id, module_name, action_name_id):
        """
        This method will redirect to a form and open in edit mode
        :param form_view: Form view name
        :param res_id: ID of element will be shown in the form
        :param module_name: name of module
        :param action_name_id: id name of action
        :return: a dictionary to render an edited form
        """
        action = self.get_action_from_action_name_id(module_name, action_name_id)
        action.update({
            'view_type': 'form',
            'view_mode': 'form',
            'views': [[self.env.ref(form_view).id, 'form']],
            'res_id': res_id,
            'context': self._context.copy(),
            'flags': {'mode': 'edit'},
        })

        return action

    def get_action_from_action_name_id(self, module_name, action_name_id):
        ir_model_obj = self.env[IR_MODEL_DATA]
        model, action_id = ir_model_obj.get_object_reference(module_name, action_name_id)
        [action] = self.env[model].browse(action_id).read()

        return action
