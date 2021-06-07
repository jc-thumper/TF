# -*- coding: utf-8 -*-

from . import utils

INDEX_VIEW_ID = 0
INDEX_VIEW_MODE = 1


def update_views(action, view_mode, view_id):
    # do not use for each because it loops by copy of element
    for i, view in enumerate(action['views']):
        if view[INDEX_VIEW_MODE] == view_mode:
            # tuple is not passed by reference
            action['views'][i] = utils.update_tuple(view, INDEX_VIEW_ID, view_id)
            return


def find_action_id(action):
    return utils.find_id(action['xml_id'])
