# -*- coding: utf-8 -*-

# CONSTANTS
# HTTP Code
HTTP_200_OK = 200
HTTP_201_OK = 201
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_404_NOT_FOUND = 404
HTTP_409_CONFLICT = 409

# HTTP Message
HTTP_200_MSG = 'Success'
HTTP_201_MSG = 'Success'
HTTP_400_MSG = 'Bad Request'
HTTP_401_MSG = 'Unauthorized'
HTTP_404_MSG = 'Not Found'
HTTP_409_MSG = 'Conflict'


def create_response_message(success, code, res_msg, **kwargs):
    """
    Create JSON response request
    :type success: bool
    :type code: int
    :type res_msg: string
    :type kwargs:
    :return:
    :rtype: dict
    """
    response_msg = {
        "success": success,
        "code": code,
        "res_msg": res_msg
    }
    response_msg.update(kwargs)
    return response_msg
