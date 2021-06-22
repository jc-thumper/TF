# -*- coding: utf-8 -*-


def find_id(external_id):
    if external_id:
        delimiter = external_id.find('.')
        if delimiter > 0:
            return external_id[(delimiter + 1):]
    return False


def update_tuple(src_tuple, modify_index, new_value):
    src_list = list(src_tuple)
    src_list[modify_index] = new_value
    return tuple(src_list)


def has_multi_currency_group(self):
    return self.env.user.has_group('base.group_multi_currency')
