# -*- coding: utf-8 -*-

########################################################
# CONSTANT VARIABLES
########################################################

class ExpirationState:
    """
        un_registered -> (registered but) not_licensed -> licensed -> no_safety_expired -> will_be_expired_today -> expired
        or
        un_registered -> un_registered_timeout
    """
    UN_REGISTERED = 'un_registered'
    UN_REGISTERED_TIMEOUT = 'un_registered_timeout'
    NOT_LICENSED = 'NOT_LICENSED'
    LICENSED = 'LICENSED'
    NO_SAFETY_EXPIRED = 'no_safety_expired'
    WILL_BE_EXPIRED_TODAY = 'will_be_expired_today'
    EXPIRED = 'expired'


class ExpirationBannerClass:
    PRIMARY = 'alert-primary'
    INFO = 'alert-info'
    WARNING = 'alert-warning'
    ERROR = 'alert-danger'
    DANGER = 'alert-danger'
    SUCCESS = 'alert-success'
