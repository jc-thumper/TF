# -*- coding: utf-8 -*-

import base64
import json
from datetime import datetime, timezone

import requests
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from psycopg2 import DatabaseError

from odoo.addons.si_core.utils.string_utils import random_pass, hash_password, check_password
from odoo.addons.si_core.utils.response_message_utils import HTTP_400_BAD_REQUEST, create_response_message
from odoo.addons.si_core.utils.request_utils import ServerAPIv1, ServerAPICode, DOMAIN_SERVER_SI
from odoo.addons.si_core.utils.datetime_utils import DEFAULT_DATE_FORMAT, convert_from_str_date_to_datetime

from ..utils.string_utils import ExpirationState
from ..utils.config_utils import MAX_RETRIES_ON_REGISTER_FAILURE, INSTANTLY_UPDATE_DEFAULT, NO_SAFETY_EXPIRE_DATE

from odoo.addons.queue_job.exception import RetryableJobError
from odoo.addons.queue_job.job import job

_logger = logging.getLogger(__name__)


class SIConfigSettings(models.TransientModel):
    """
        This model create a table in database to store configurations
        for forecast demand application.
    """
    _name = "forecasting.config.settings"
    _description = "Forecasting Configuration Settings"

    ########################################################
    # FIELD VALUES
    ########################################################
    si_uuid = fields.Char('SI\'s UID', default='', store=True)
    si_server_pass = fields.Char('SI\'s server password', default='', store=True)

    percentage_level_a = fields.Float(required=True, default=0.96)
    percentage_level_b = fields.Float(required=True, default=0.92)
    percentage_level_c = fields.Float(required=True, default=0.85)
    instantly_update = fields.Boolean(required=True, default=True, help='')

    setup_status = fields.Boolean(required=True, default=False, help='')
    server_available = fields.Boolean(required=True, default=False,
                                      help='The FE server status that is ready to call or not')
    client_available = fields.Boolean(required=True, default=False,
                                      help='The Odoo server status that is ready to client can use or not')

    ########################################################
    # COMPUTE FUNCTIONS
    ########################################################

    ########################################################
    # ONCHANGE EVENT
    ########################################################

    ########################################################
    # GENERAL FUNCTIONS
    ########################################################
    @api.model
    def get_values(self):
        res = {}
        get_param = self.env['forecasting_config_parameter'].sudo().get_param
        res.update(si_uuid=get_param('forecasting.si_uuid', ''),
                   si_server_pass=get_param('forecasting.si_server_pass', ''),
                   percentage_level_a=get_param('forecasting.percentage_level_a', '0.96'),
                   percentage_level_b=get_param('forecasting.percentage_level_b', '0.92'),
                   percentage_level_c=get_param('forecasting.percentage_level_c', '0.85'),
                   instantly_update=get_param('forecasting.instantly_update', 'True'),
                   setup_status=get_param('forecasting.setup_status', 'False'),
                   server_available=get_param('forecasting.server_available', 'False'),
                   client_available=get_param('forecasting.client_available', 'False'),
                   )
        return res

    def set_values(self):
        set_param = self.env['forecasting_config_parameter'].sudo().set_param
        set_param('forecasting.si_uuid', self.si_uuid)
        set_param('forecasting.si_server_pass', self.si_server_pass)
        set_param('forecasting.percentage_level_a', str(self.percentage_level_a))
        set_param('forecasting.percentage_level_b', str(self.percentage_level_b))
        set_param('forecasting.percentage_level_c', str(self.percentage_level_c))
        set_param('forecasting.instantly_update', str(self.instantly_update))
        set_param('forecasting.setup_status', str(self.setup_status))
        set_param('forecasting.server_available', str(self.server_available))
        set_param('forecasting.client_available', str(self.client_available))

    @api.model
    def default_get(self, fields_list):
        defaults = super(SIConfigSettings, self).default_get(fields_list)
        defaults.update(self.get_values())
        return defaults

    ########################################################
    # PRIVATE FUNCTIONS
    ########################################################
    def _request_register(self, client_pass):
        """

        :return:
        """
        domain_name = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        from . import APP_VERSION
        data = {
            'client_pass': client_pass,
            'domain_name': domain_name,
            'version': APP_VERSION
        }

        direct_order_url = ServerAPIv1.get_api_url(ServerAPICode.REGISTER)

        _logger.info("Call API to register SI service")
        headers = {
            'Content-type': 'application/json',
            # 'Accept': 'text/plain'
        }
        return requests.post(direct_order_url, data=json.dumps(data),
                             headers=headers, timeout=60)

    ########################################################
    # PUBLIC FUNCTIONS
    ########################################################
    @staticmethod
    def create_si_information(context, uid, server_pass):
        """ Update uid and server pass to environment of odoo database

        :param context:
        :param uid:
        :type uid: str
        :param server_pass:
        :type server_pass: str
        :return: None
        """
        if uid and server_pass:
            set_param = context.env['forecasting_config_parameter'].sudo().set_param
            set_param('forecasting.si_uuid', uid)
            hash_passwd = hash_password(server_pass)
            logging.info("Password user uid %s has been hashed: %s", uid, hash_passwd)
            set_param('forecasting.si_server_pass', hash_passwd)

    @staticmethod
    def check_has_registered_si(context):
        """ Update uid and server pass to environment of odoo database

        :param context:
        :return:
        :rtype: bool
        """
        has_registered = False
        get_param = context.env['forecasting_config_parameter'].sudo().get_param
        si_uuid = get_param('forecasting.si_uuid', default='')
        si_server_pass = get_param('forecasting.si_server_pass', default='')
        if si_uuid and si_server_pass:
            has_registered = True
        else:
            context.create_si_information(context, '', '')
        return has_registered

    def change_setup_status(self, setup_status):
        self.env['forecasting_config_parameter'] \
            .sudo() \
            .set_param('forecasting.setup_status', setup_status)

    def change_server_available(self, server_available):
        self.env['forecasting_config_parameter'] \
            .sudo() \
            .set_param('forecasting.server_available', server_available)

    def change_client_available(self, client_available):
        """

        :param client_available:
        :type client_available: bool
        :return:
        """
        self.env['forecasting_config_parameter'] \
            .sudo() \
            .set_param('forecasting.client_available', client_available)

    @job(retry_pattern={1: 1 * 60,
                        3: 5 * 60},
         default_channel='root.forecasting')
    def cron_check_client_available(self):
        _logger.info('Check client available with Engine')
        try:
            # just comment to test, please don't remove this comment code
            # client_available = self._get_client_available_status()
            client_available = True
            if client_available:
                self.change_client_available(True)
            else:
                # Re-check it after 5 minute
                self.with_delay(eta=60 * 3).cron_check_client_available()
        except Exception as e:
            _logger.exception('Function update_forecast_result_base_on_write_time have some exception: %s' % e)
            raise RetryableJobError('Must be retried later')

    def _get_client_available_status(self):
        """
        Check number records in Forecast Result and Forecast Result Adjust to know
        we can display forecast chart for products or not.
        :return:
        :rtype: bool
        """
        no_fore_results, fore_pub_time = self.env['forecast.result'].get_no_nearest_forecast_results()
        no_adjust_items = self.env['forecast.result.adjust'].get_no_available_adjust_items(pub_time=fore_pub_time)
        client_status = no_adjust_items == no_fore_results
        _logger.info("Client available status: %s", client_status)
        return client_status

    @staticmethod
    def check_si_pass(context, server_pass):
        """

        :param context:
        :param server_pass:
        :return:
        """
        set_param = context.env['forecasting_config_parameter'].sudo().set_param
        model = context.env['forecasting_config_parameter'].sudo()

        hashed_password = model._get_hashed_password()
        valid, replacement = check_password(server_pass, hashed_password)

        if valid and replacement:  # update password if server password is valid
            set_param('forecasting.si_server_pass', replacement)
        return valid

    @staticmethod
    def check_si_availability(context):
        """ Function check weather SI service has been available or not

        :param context: in normal case it is 'self' variable
        :return bool: True if SI service has been available
        """
        get_param = context.env['forecasting_config_parameter'].sudo().get_param
        uuid = get_param('forecasting.si_uuid', '')
        server_pass = get_param('forecasting.si_server_pass', '')
        status = True
        if not uuid or not server_pass:
            status = False

        _logger.debug('Check SI availability: Status-{status}; uuid-{uuid}; server_pass-{server_pass}'.format(
            status=status,
            uuid=uuid,
            server_pass=server_pass
        ))
        return status

    def check_setup_status(self):
        """

        :return:
        :rtype: bool
        """
        setup_status = self.env['forecasting_config_parameter'] \
            .sudo() \
            .get_param('forecasting.setup_status', False)
        return setup_status == 'True'

    def check_server_available(self):
        """

        :return:
        :rtype: bool
        """
        server_available = self.env['forecasting_config_parameter'] \
            .sudo() \
            .get_param('forecasting.server_available', False)
        return server_available == 'True'

    def check_client_available(self):
        """

        :return:
        :rtype: bool
        """
        client_available = self.env['forecasting_config_parameter'] \
            .sudo() \
            .get_param('forecasting.client_available', False)
        return client_available == 'True'

    def check_instantly_update(self):
        try:
            instantly_update = self.env['forecasting_config_parameter'] \
                .sudo() \
                .get_param('forecasting.instantly_update', None)
            _logger.warning('----> %s: %s' % (instantly_update, datetime.now()))
            if instantly_update is None:
                _logger.warning('%s - %s' % (instantly_update, datetime.now()))
                self.env['forecasting_config_parameter'] \
                    .sudo() \
                    .set_param('forecasting.instantly_update', INSTANTLY_UPDATE_DEFAULT)
                instantly_update = INSTANTLY_UPDATE_DEFAULT
            return instantly_update
        except Exception as e:
            _logger.exception("There was some problems when checking instantly update.", exc_info=True)
            raise e

    def get_auth_content(self):
        auth_content = {}
        si_fe_uuid = self.sudo().env['forecasting.config.settings'].get_fe_uuid()
        si_fe_pass = self.sudo().env['forecasting.config.settings'].get_fe_pass()
        if si_fe_pass and si_fe_uuid:
            auth_content = {
                'uuid': si_fe_uuid,
                'password': si_fe_pass
            }
        return auth_content

    def get_fe_uuid(self):
        get_param = self.env['forecasting_config_parameter'].sudo().get_param
        si_uuid = get_param('forecasting.si_uuid', None)
        return si_uuid

    def get_fe_pass(self):
        get_param = self.env['forecasting_config_parameter'].sudo().get_param
        enc_fe_pass = get_param('forecasting.si_fe_key', None)
        dec_fe_pass = enc_fe_pass and self.decryption_password(enc_fe_pass)
        return dec_fe_pass

    def set_fe_pass(self, fe_pass):
        enc_fe_pass = self.encrypt_password(fe_pass)
        set_param = self.env['forecasting_config_parameter'].sudo().set_param
        set_param('forecasting.si_fe_key', enc_fe_pass)

    ###############################
    # INITIAL FUNCTIONS
    ###############################
    def _register_service(self):
        """
        Handler the logic when register SI service
        :return: JSON response of the request; return a empty dictionary when has registered before
        :rtype: dict
        """
        result_json = {}
        has_registered = self.check_has_registered_si(self)
        _logger.debug('Has been registered FE service: %s' % has_registered)
        if not has_registered:
            client_pass = random_pass(10)
            response = self._request_register(client_pass)
            response.raise_for_status()
            result_json = response.json()
            _logger.info("Register response code: %s" % result_json.get('code'))

            if result_json.get('code') == 201:
                uid = result_json['result']['UID']
                if uid:
                    self.set_fe_pass(client_pass)
                    server_pass = result_json['result']['server_pass']
                    self.create_si_information(self, uid, server_pass)
            else:
                _logger.warning('Error message: %s', result_json.get('res_msg'))

        return result_json

    @api.model
    def register_service(self):
        """
        Send request to the server to register SI service
        :return:
        """
        _logger.info("register SI service")

        try:
            self._register_service()
        except ValueError as val_error:
            raise ValueError(_('Response Json format is wrong: %s' % val_error))
        except requests.exceptions.ConnectionError:
            _logger.error(_('Server not reachable, please try again later'), exc_info=True)
        except requests.exceptions.Timeout:
            _logger.exception(_('Timeout: the server did not reply within 60s'), exc_info=True)
        except DatabaseError:
            _logger.exception(_('Database error occur when register SI service'), exc_info=True)
        except Exception:
            _logger.exception(_('Exception occur when register SI service'), exc_info=True)

        has_registered = self.check_has_registered_si(self)
        if has_registered:
            self._request_sync_license_info()

    SALT_LENGTH = 16
    ENCRYPT_PASS = 'P4ssw0rd_c13nt'

    @staticmethod
    def encrypt_password(plain_text):
        salt = bytes(random_pass(SIConfigSettings.SALT_LENGTH), 'utf-8')
        encrypted_text = SIConfigSettings._encrypt(plain_text, salt)
        encrypted_pass = salt + encrypted_text
        return encrypted_pass

    @staticmethod
    def decryption_password(encrypted_pass):
        salt = bytes(encrypted_pass[:SIConfigSettings.SALT_LENGTH], 'utf-8')
        pass_detail = bytes(encrypted_pass[SIConfigSettings.SALT_LENGTH:], 'utf-8')
        password = SIConfigSettings._decrypt(pass_detail, salt)
        return password

    ########################################################
    # PRIVATE FUNCTIONS
    ########################################################
    @staticmethod
    def _get_encrypt_func(salt):
        password_provided = SIConfigSettings.ENCRYPT_PASS
        password = password_provided.encode()  # Convert to type bytes
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))  # Can only use kdf once
        func_encrypt = Fernet(key)
        return func_encrypt

    @staticmethod
    def _encrypt(plain_text, salt):
        func_encrypt = SIConfigSettings._get_encrypt_func(salt)
        encoded_text = plain_text.encode()
        encrypted = func_encrypt.encrypt(encoded_text)
        return encrypted

    @staticmethod
    def _decrypt(encrypted_text, salt):
        func_encrypt = SIConfigSettings._get_encrypt_func(salt)
        decrypted = func_encrypt.decrypt(encrypted_text)
        decoded_text = decrypted.decode()
        return decoded_text

    def _request_sync_license_info(self):
        """
            This function is used for synchronizing license info with server
        :return: dict
        """
        get_param = self.env['forecasting_config_parameter'].sudo().get_param

        # Get all expiration variables from local
        expiration_state = get_param('forecasting.expiration_state', ExpirationState.UN_REGISTERED)
        expiration_days_left = get_param('forecasting.expiration_days_left', 0)
        forecasting_service_plan = get_param('forecasting.forecasting_service_plan', '')

        # If register timeout, don't need to sync license info
        if expiration_state == ExpirationState.UN_REGISTERED_TIMEOUT:
            return

        # If not register timeout
        direct_order_url = ServerAPIv1.get_api_url(ServerAPICode.CHECK_LICENSE_KEY)
        headers = {
            'Content-type': 'application/json',
        }

        auth_content = SIConfigSettings.get_auth_content(self)
        # If there's auth_info -> Successful register to server
        if auth_content:
            # Request server to get the license info
            json_body = json.dumps(auth_content)
            response = requests.post(direct_order_url, data=json_body, headers=headers, timeout=60)
            try:
                result = response.json()
            except Exception as e:
                _logger.error("There some problems when parsing JSON in _request_sync_license_info function.", exc_info=True)
                raise e

            # Check the license info
            license_response_code = result.get('license_response_code', '')
            if license_response_code == ExpirationState.NOT_LICENSED:
                expiration_state = ExpirationState.NOT_LICENSED

            elif license_response_code == ExpirationState.LICENSED:
                data = result.get('data', [{}])[0]

                odoo_now_str = datetime.now().date().strftime(DEFAULT_DATE_FORMAT)
                expiry_date_str = data.get('expiry_date', False)
                converted_expiry_date = convert_from_str_date_to_datetime(expiry_date_str).date()
                number_of_diff_date = (converted_expiry_date - datetime.now(tz=timezone.utc).date()).days

                expiry_reason = data.get('expiry_reason', '7-day-free trial')
                expiration_days_left = number_of_diff_date
                forecasting_service_plan = expiry_reason

                # If the expiration date is today
                if number_of_diff_date == 0:
                    expiration_state = ExpirationState.WILL_BE_EXPIRED_TODAY

                # If the expiration date is in the past
                elif expiry_date_str < odoo_now_str:
                    expiration_state = ExpirationState.EXPIRED

                    # The license has expired. Set the limit of forecast item to default value

                # If the license has not expired, but it is in the un-safe period
                elif number_of_diff_date <= NO_SAFETY_EXPIRE_DATE:
                    expiration_state = ExpirationState.NO_SAFETY_EXPIRED

                # Unless, it's in the safety period
                else:
                    expiration_state = ExpirationState.LICENSED
            else:
                expiration_state = ExpirationState.UN_REGISTERED
        else:
            # If the cron reach the MAX_RETRIES_ON_REGISTER_FAILURE -> The cron no longer runnable
            ir_cron = self.env['ir.cron'].with_context(active_test=False).search(
                [('cron_name', 'like', 'Retry: Register SI service%')],
                limit=1,
            )
            register_cron_number_call = ir_cron.numbercall
            if register_cron_number_call == 0:
                expiration_state = ExpirationState.UN_REGISTERED_TIMEOUT

        set_param = self.env['forecasting_config_parameter'].sudo().set_param

        set_param('forecasting.expiration_state', expiration_state)
        set_param('forecasting.expiration_days_left', expiration_days_left)
        set_param('forecasting.forecasting_service_plan', forecasting_service_plan)

    ########################################################
    # CRON JOB
    ########################################################
    def _cron_retry_register_si_service(self):
        """

        :return:
        """
        logging.info('Start the cron job to retry register SI service')

        # check the status of event register SI service
        status = self.check_si_availability(self)

        result_json = None
        if status:
            # retry register SI service success
            _logger.info("Retry register SI service success.")
        else:
            try:
                result_json = self._register_service()

                # Run when retry to register success
                if result_json:
                    # register successful
                    if result_json.get('code') == 201:
                        self._cron_request_sync_license_info()

                    ir_cron = self.env['ir.cron'].with_context(active_test=False).search(
                        [('cron_name', 'like', 'Retry: Register SI service%')],
                        limit=1)

                    # get the number re-register logged on the number of times call cron
                    numbercall = ir_cron.numbercall
                    retry_count = MAX_RETRIES_ON_REGISTER_FAILURE - numbercall + 1
                    retry_count += 1

                    _logger.info('Retry register SI service %d/%d ...' %
                                 (retry_count, MAX_RETRIES_ON_REGISTER_FAILURE))

                    if retry_count >= MAX_RETRIES_ON_REGISTER_FAILURE:
                        _logger.error('Maximum number of tries register SI service reached.')
                        domain_name = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                        data = {
                            'code': HTTP_400_BAD_REQUEST,
                            'res_msg': 'Register failed the domain name %s with error message %s.'
                                       % (domain_name, result_json.get('res_msg'),)
                        }

                        URL = DOMAIN_SERVER_SI + '/api/register_notification/'

                        headers = {
                            'Content-type': 'application/json',
                        }

                        requests.post(URL, data=json.dumps(data),
                                      headers=headers, timeout=60)
                else:
                    _logger.warning("Something were wrong when retry to register.")

            except ValueError:
                raise ValueError(_('Response Json format is wrong: %s' % result_json))
            except requests.exceptions.ConnectionError:
                _logger.error(_('Server not reachable, please try again later'), exc_info=True)
            except requests.exceptions.Timeout:
                raise UserError(_('Timeout: the server did not reply within 60s'), exc_info=True)
            except Exception as e:
                _logger.exception(_('There was some problems when register SI server.'), exc_info=True)
                raise e

    def _cron_request_sync_license_info(self):
        """
            This cron will run once a day to update license info automatically
        :return: dict
        """
        self._request_sync_license_info()
