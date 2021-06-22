# -*- coding: utf-8 -*-


import re

check_expression = re.compile('check .*|.* check .*|.* check', re.IGNORECASE)
check_number_with_double_separators = re.compile('[(\[{"\'#]\d+[)\]}"\'#]')
check_number_with_single_separator = re.compile('#\d+')
check_number_without_separator = re.compile('\d+')


def is_check_statement(description):
    """
    If description of bank statement line has "check" word, we will return True. Otherwise, return False.
    :param description:
    :return:
    """
    return description and check_expression.fullmatch(description) is not None


def extract_check_number(description):
    """
    Recognize check number and return
    :param description:
    :return: check number
    """
    for word in description.split(' '):
        if check_number_with_double_separators.fullmatch(word):
            return word[1:-1]
        elif check_number_with_single_separator.fullmatch(word):
            return word[1:]
        elif check_number_without_separator.fullmatch(word):
            return word

    return None
