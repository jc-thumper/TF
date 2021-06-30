# -*- coding: utf-8 -*-

from datetime import datetime


def create_file(file_name_origin, file_content, time_info=True, format_time_info="%Y-%m-%d-%H-%M-%S"):
    """
    Store the data to a file named file_name_%Y-%m-%d-%H-%M-%S.txt
    :param file_name_origin:
    :type file_name_origin: str
    :param file_content:
    :type file_content: str
    :param time_info:
    :type time_info: bool
    :type format_time_info: str
    :return:
    """
    from odoo.tools import config
    log_engine_file = config.get("log_engine_file", False)

    if log_engine_file:
        file_name = _get_file_name(file_name_origin, time_info, format_time_info)
        full_file_name = '%s.txt' % file_name
        f = open(full_file_name, "w+")
        f.write(file_content)
        f.close()


def read_file(file_name_origin, time_info=True, format_time_info="%Y-%m-%d-%H-%M-%S"):
    """
    Read the data to a file named file_name_%Y-%m-%d-%H-%M-%S.txt
    :param file_name_origin:
    :type file_name_origin: str
    :param time_info:
    :type time_info: bool
    :type format_time_info: str
    :return:
    :rtype: str
    """
    from os import listdir
    from os.path import isfile
    from odoo.tools import config
    log_engine_file = config.get("log_engine_file", False)

    content = ''

    if log_engine_file:
        files = [f for f in listdir() if isfile(f) and f.startswith(file_name_origin)]

        if files:
            # we make assumption the format_time_info help the file order by create time
            latest_file = max(files)
            if time_info:
                create_info = latest_file[len(file_name_origin) + 1:-4]

                create_at = datetime.strptime(create_info, format_time_info)
                if (datetime.now() - create_at).days <= 1:
                    f = open(latest_file, "r")
                    content = f.read()
                    f.close()
            else:
                f = open(latest_file, "r")
                content = f.read()
                f.close()
    return content


def _get_file_name(file_name_origin, time_info, format_time_info):
    """

    :param file_name_origin:
    :type file_name_origin: str
    :param time_info:
    :type time_info: bool
    :param format_time_info:
    :type format_time_info: str
    :return:
    :rtype: str
    """
    if time_info:
        file_name = '_'.join([file_name_origin, datetime.now().strftime(format_time_info)])
    else:
        file_name = file_name_origin
    return file_name
