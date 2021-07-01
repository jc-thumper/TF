# -*- coding: utf-8 -*-

import hashlib
import os
import random
import binascii
import passlib.context
import numpy as np

from datetime import datetime
from odoo import _

########################################################
# CONSTANT VARIABLES
########################################################

DEFAULT_CRYPT_CONTEXT = passlib.context.CryptContext(
    # kdf which can be verified by the context. The default encryption kdf is
    # the first of the list
    ['pbkdf2_sha512', 'plaintext'],
    # deprecated algorithms are still verified as usual, but ``needs_update``
    # will indicate that the stored hash should be replaced by a more recent
    # algorithm. Passlib 1.6 supports an `auto` value which deprecates any
    # algorithm but the default, but Ubuntu LTS only provides 1.5 so far.
    deprecated=['plaintext'],
)

NO_MAGIC_CHARACTER = 5


class PeriodType:
    HOURLY_TYPE = 'hourly'
    DAILY_TYPE = 'daily'
    WEEKLY_TYPE = 'weekly'
    MONTHLY_TYPE = 'monthly'
    QUARTERLY_TYPE = 'quarterly'
    YEARLY_TYPE = 'yearly'
    BIWEEKLY = 'biweekly'

    DEFAULT_PERIOD_TYPE = WEEKLY_TYPE

    LIST_PERIODS = [
        (DAILY_TYPE, 'Daily'),
        (WEEKLY_TYPE, 'Weekly'),
        (MONTHLY_TYPE, 'Monthly'),
        (QUARTERLY_TYPE, 'Quarterly'),
        (YEARLY_TYPE, 'Yearly')]

    PERIOD_INFO = {
        DAILY_TYPE: ['day', '1 day'],
        WEEKLY_TYPE: ['week', '1 week'],
        MONTHLY_TYPE: ['month', '1 month'],
        QUARTERLY_TYPE: ['quarter', '3 month'],
        YEARLY_TYPE: ['year', '1 year'],
    }

    # use to create Forecasting Frequency
    ORDERED_FORECASTING_FREQUENCY = [
        (DAILY_TYPE, 'Daily'),
        (WEEKLY_TYPE, 'Weekly'),
        (BIWEEKLY, 'Biweekly'),
        (MONTHLY_TYPE, 'Monthly'),
        (QUARTERLY_TYPE, 'Quarterly')]

    FORECASTING_FREQUENCY_RANK = {
        DAILY_TYPE: 0,
        WEEKLY_TYPE: 1,
        BIWEEKLY: 2,
        MONTHLY_TYPE: 3,
        QUARTERLY_TYPE: 4
    }

    PERIOD_SIZE = {
        DAILY_TYPE: 1,
        WEEKLY_TYPE: 7,
        MONTHLY_TYPE: 30.4375,
        QUARTERLY_TYPE: 91.3125,
        YEARLY_TYPE: 365
    }

    PERIODS_TO_FORECAST = {
        DAILY_TYPE: 31,
        WEEKLY_TYPE: 52,
        MONTHLY_TYPE: 12,
        QUARTERLY_TYPE: 4,
        YEARLY_TYPE: 2
    }

    # use to set the time for cron-job
    REALTIME_VALUE = 'real_time'
    TIME_INTERVAL_VALUE = 'time_interval'

    TIME_OPTION_SELECTION = [(REALTIME_VALUE, _('Refresh On Dashboard Load')),
                             (TIME_INTERVAL_VALUE, _('Time Interval'))]

    TIME_INTERVAL_SELECTION = [('minutes', _('minute(s)')),
                               ('hours', _('hour(s)')),
                               ('days', _('day(s)'))]

    @classmethod
    def generate_period_label(cls, start_date, end_date, invest_type):
        """

        :param invest_type:
        :param start_date:
        :type start_date: datetime
        :param end_date:
        :type end_date: datetime
        :return:
        """
        label = ''
        if invest_type == cls.DAILY_TYPE:
            label = start_date.strftime('%d %B %Y')
        elif invest_type == cls.WEEKLY_TYPE:
            label = '%s-%s' % (start_date.strftime('%d'), end_date.strftime('%d %b'))
        elif invest_type == cls.MONTHLY_TYPE:
            format_date = '%b, %Y'
            label = '%s' % start_date.strftime(format_date)
        elif invest_type == cls.QUARTERLY_TYPE:
            label = 'Q%s, %s' % ((end_date.month - 1) // 3 + 1, end_date.strftime('%Y'))
        elif invest_type == cls.YEARLY_TYPE:
            format_date = '%Y'
            label = end_date.strftime(format_date)
        return label


class ServiceLevel:
    ###############################
    # CONSTANTS
    ###############################
    CATEGORY_A = 'group_a'
    CATEGORY_B = 'group_b'
    CATEGORY_C = 'group_c'
    CATEGORY_NONE = None

    CLSF_NAME = [
        ('group_a', 'Group A'),
        ('group_b', 'Group B'),
        ('group_c', 'Group C')
    ]


class ProductLeadTimeConfig:
    AVG_LEADTIME = 'avg'
    LOWEST_COST_LEADTIME = 'lowest_cost'


########################################################
# HELPER FUNCTION
########################################################

def random_pass(pass_len):
    """
    Function random a password
    :param int pass_len: length of password
    :return string: a password random
    """
    available_symbol = "abcdefghijklmnopqrstuvwxyz01234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()?_-"
    p = "".join(random.sample(available_symbol, pass_len))
    return p


def encrypt_client_password(password):
    """Hash a password for storing."""
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 10)
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')


def create_magic_pass(password):
    """ create a magic pass to hacker can not trace back by replace hash value

    :param password:
    :type password: str
    :return:
    :rtype: str
    """
    return password[-NO_MAGIC_CHARACTER:] + password + password[:NO_MAGIC_CHARACTER]


def hash_password(password):
    """ Function return the hash value of password

    :param password:
    :return:
    :rtype: str
    """
    context = _crypt_context()
    magic_pass = create_magic_pass(password)
    hashed_pass = context.encrypt(magic_pass)
    return hashed_pass


def check_password(password, hashed):
    """ Function check the entered password are right or wrong

    :param password: the password need to check
    :type password: str
    :param hashed: the hash value on the database
    :type hashed: str
    :return:
    :rtype: bool
    """
    magic_pass = create_magic_pass(password)
    valid, replacement = _crypt_context() \
        .verify_and_update(magic_pass, hashed)
    return valid, replacement


########################################################
# PRIVATE FUNCTIONS
########################################################
def _crypt_context():
    """ Passlib CryptContext instance used to encrypt and verify
    passwords. Can be overridden if technical, legal or political matters
    require different kdfs than the provided default.

    Requires a CryptContext as deprecation and upgrade notices are used
    internally
    """
    return DEFAULT_CRYPT_CONTEXT


########################################################
# PUBLIC FUNCTIONS
########################################################

def get_table_name(table_name=''):
    """
    Convert the field _name in the model in Odoo to
    the table name in the database
    :param table_name: the name of a model, for example: sale.order.line
    :return: table name of this model in the database
    _name = "sale.order.line" => sale_order_line
    """
    assert table_name, "Table name cannot be empty"
    return '_'.join(table_name.split('.'))


def get_unique_items(data, new_values=None):
    """
    Find the unique value in a list of string
    :type data: a list of str
    :param new_values: new values to append to the ``data``
    :type new_values: a list of str
    :return:
    """
    # strim white space in each item in the list
    strimed_values = [item.strip() for item in data]

    result = np.unique(strimed_values + new_values) if new_values else np.unique(strimed_values)

    return result
