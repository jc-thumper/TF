# -*- coding: utf-8 -*-

from operator import itemgetter


def filter_rows_by_tuple(df, list_of_keys, list_of_values):
    """
    Filter rows by tuple of keys
    :param pandas.core.frame.DataFrame df:
    :param list[str] list_of_keys: fields to get values in `list_of_values`
    :param list[tuple] list_of_values: values corresponding with the order of field name
    :return list:
    """
    result = []
    if df.empty is False:
        new_df = df.copy()

        new_df['grouped_keys'] = df[list_of_keys].apply(lambda row: itemgetter(*list_of_keys)(row), axis=1)
        new_df['is_selected'] = new_df.apply(lambda row: row['grouped_keys'] in list_of_values, axis=1)
        result = new_df['is_selected'].values.tolist()
    return result
