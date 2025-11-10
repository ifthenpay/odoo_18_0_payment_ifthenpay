# -*- coding: utf-8 -*-
import json
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.http import request
from urllib.parse import quote
import logging

from odoo.addons.payment_ifthenpay_oficial import const

_logger = logging.getLogger(__name__)

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('ifthenpay', 'ifthenpay')], ondelete={'ifthenpay': 'set default'}
    )
    
    # --- Campos de Configuração da ifthenpay ---
    ifthenpay_api_key = fields.Char(_("ClientID (backoffice)"), required_if_provider='ifthenpay', groups='base.group_user', help=_("The ClientID provided by ifthenpay."))
    ifthenpay_email_account = fields.Char(
        string=_("E-mail"),
        help=_("The public business email solely used to identify the account with ifthenpay"),
        default=lambda self: self.env.company.email,
        readonly=True
    )
    ifthenpay_store_name = fields.Char(_("Store name"), groups='base.group_user', help=_("Name of your store."), readonly=True)
    ifthenpay_gateway_key = fields.Char(_("Gateway Key"), groups='base.group_user', required_if_provider='ifthenpay', help=_("Gateway Key provided by ifthenpay."), readonly=True)
    ifthenpay_expiry_days = fields.Char(_("Deadline"), groups='base.group_user', help=_("Payment link expiration period."), readonly=True)
    url_base = fields.Char(_("URL"), groups='base.group_user', help=_("Store URL."), readonly=True)
    ifthenpay_accounts_info = fields.Text(
        string=_("Accounts"),
        help=_("List of accounts or data provided by ifthenpay. One per line."),
        readonly=True
    )

    def _get_api_url(self):
        self.ensure_one()
        if self.state != 'enabled':
            return None
        return 'https://api.ifthenpay.com/gateway/pinpay/'

    def _get_pay_form_inputs(self, transaction_values):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        
        # 'transaction_values' é o dicionário de dados da transação do Odoo
        ifthenpay_tx_values = {
            'chave': self.ifthenpay_api_key,
            'referencia': transaction_values['reference'],
            'valor': "%.2f" % transaction_values['amount'],
            'moeda': transaction_values['currency'].name,
            'store_name': self.ifthenpay_store_name,
            'email_account': self.ifthenpay_email_account,
            'url_back': '%s/payment/ifthenpay/return' % base_url,
            'url_cancel': '%s/payment/ifthenpay/cancel' % base_url,
            'ifthenpay_gateway_key': self.ifthenpay_gateway_key,
            'ifthenpay_expiry_days': self.ifthenpay_expiry_days,
            'url_base': self.url_base, 
            # Adicionar outros parâmetros específicos
        }

        return ifthenpay_tx_values

    def _get_form_action_url(self, transaction_values): 
        self.ensure_one()
        return self._get_api_url() + '/createPayment'

    def _ifthenpay_verify_signature(self, incoming_values):
        return True

    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'ifthenpay':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'ifthenpay':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES
    
    def _ifthenpay_get_inline_form_values(self, currency=None):
        """ Return a serialized JSON of the required values to render the inline form.

        Note: `self.ensure_one()`

        :param res.currency currency: The transaction currency.
        :return: The JSON serial of the required values to render the inline form.
        :rtype: str
        """
        inline_form_values = {
            'provider_id': self.id,
            'currency_code': currency and currency.name,
        }
        return json.dumps(inline_form_values)
    
    def _ifthenpay_api_create_payment_pinpay(self, transaction):
        """
        Makes a call to the ifthenpay API to generate the payment URL.
        :param transaction: The payment.transaction record.
        :return: A dictionary with the payment URL and any other relevant data from ifthenpay.
        :rtype: dict
        """
        self.ensure_one()
        result = self._get_integration_api(self.ifthenpay_api_key)
        if result is None:
            raise UserError(_("Unable to connect to ifthenpay because the provider is disabled."))
        
        api_url = self._get_api_url() + result.get('gatewayKey')
        if api_url is None:
            raise UserError(_("Unable to connect to ifthenpay because the provider is disabled."))

        base_url = result.get('storeUrl')
        all_fields_data = transaction.read([])

        selected_data_json_string = result.get('paymentData')
        payment_method = None


        if isinstance(selected_data_json_string, str):
            try:
                # Tenta converter a string JSON para um objeto Python
                selected_data_object = json.loads(selected_data_json_string)
                
                # Verifica se é um dicionário e se 'defaultPaymentMethod' existe nele
                if isinstance(selected_data_object, dict) and 'defaultPaymentMethod' in selected_data_object:
                    payment_method = selected_data_object['defaultPaymentMethod']
                else:
                    _logger.warning("ifthenpay: 'paymentData' eh JSON, mas 'defaultPaymentMethod' nao encontrado ou nao eh um dicionario.")
            except json.JSONDecodeError:
                _logger.warning("ifthenpay: 'paymentData' nao eh uma string JSON valida.")
            except Exception as e:
                _logger.error("ifthenpay: Erro inesperado ao processar 'paymentData': %s", e)
        else:
            _logger.warning("ifthenpay: 'paymentData' nao eh uma string.")

        cancel_url = quote(f"{base_url}/payment/ifthenpay/iframe_redirect?reference={transaction.reference}&amount={transaction.amount}&status=cancel")
        error_url = quote(f"{base_url}/payment/ifthenpay/iframe_redirect?reference={transaction.reference}&amount={transaction.amount}&status=error")
        success_url = quote(f"{base_url}/payment/ifthenpay/iframe_redirect?reference={transaction.reference}&amount={transaction.amount}&status=success&txid=[TRANSACTIONID]")

        ifthenpay_payload = {
            'id': transaction.reference,
            'amount': "%.2f" % transaction.amount,
            'description': transaction.id,
            'accounts': result.get('accountKeys'),
            'selected_method': None,
            'success_url': success_url,
            'error_url': error_url,
            'btnCloseUrl': cancel_url,
            'cms': 'ODOO',
            'expiryDays': result.get('expiryDays'),
            # 'lang': request.env.lang.split('_')[0] if requests else 'pt', # Exemplo: idioma
        }

        if payment_method:
            ifthenpay_payload['selected_method'] = payment_method

        try:
            response = requests.post(api_url, json=ifthenpay_payload, timeout=30)
            response.raise_for_status() # Lança um HTTPError para respostas de erro (4xx ou 5xx)
            api_response = response.json()

            if response.status_code == 200 and api_response.get('PinpayUrl'):
                return {'payment_url': api_response['PinpayUrl'], 'raw_response': api_response}
            else:
                error_msg = api_response.get('message', 'Erro desconhecido da API ifthenpay.')
                _logger.error("Erro da API ifthenpay: %s - Resposta completa: %s", error_msg, api_response)
                raise UserError(_("Failed to create ifthenpay payment: %s") % error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error("Erro de comunicacao com a API ifthenpay: %s", e)
            raise UserError(_("Unable to connect to ifthenpay. Please try again later."))
        except json.JSONDecodeError as e:
            _logger.error("Falha ao decodificar a resposta da API ifthenpay: %s", e)
            raise UserError(_("Invalid response from ifthenpay. Please contact support."))
    
    def _get_payment_flow(self):
        if self.code == 'ifthenpay':
            _logger.info(">>>>> Usando fluxo INLINE para ifthenpay (ID: %s)", self.id)
            return 'direct'
        return super()._get_payment_flow()
    
    def _get_integration_api(self, token):
        self.ensure_one()
        try:
            if self.state != 'enabled':
                _logger.error("Erro por nao habilitar provider")
                return None

            url = f'https://api.ifthenpay.com/v2/cmsintegration/get/{token}/odoo'

            response = requests.post(url, timeout=60)
            response.raise_for_status()
            api_response = response.json()

            if response.status_code == 200:
                return api_response
            else:
                error_msg = api_response.get('message', 'Erro desconhecido da API ifthenpay.')
                _logger.error("Erro da API ifthenpay: %s - Resposta completa: %s", error_msg, api_response)
                raise UserError(_("Failed to create ifthenpay payment: %s") % error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error("Erro de comunicação com a API ifthenpay: %s", e)
            raise UserError(_("Unable to connect to ifthenpay."))
        except json.JSONDecodeError as e:
            _logger.error("Falha ao decodificar a resposta da API ifthenpay: %s", e)
            raise UserError(_("Invalid response from ifthenpay. Please contact support."))
    
    @api.onchange('ifthenpay_api_key')
    def _onchange_ifthenpay_api_token(self):
        if not self.ifthenpay_api_key:
            self.ifthenpay_store_name = ''
            self.ifthenpay_email_account = ''
            self.ifthenpay_gateway_key = ''
            self.ifthenpay_expiry_days = ''
            self.ifthenpay_accounts_info = ''
            self.url_base = ''
            return

        try:
            result = self._get_integration_api(self.ifthenpay_api_key)
            if result is None:
                raise UserError(_("Unable to connect to ifthenpay because the provider is disabled."))
            
            accounts = result.get('accountKeys')

            cleaned_lines = []
            for part in accounts.split(";"):
                cleaned_lines.append(part.strip()) 

            self.ifthenpay_accounts_info = "\n".join(cleaned_lines)

            base_url = result.get('storeUrl')
            self.ifthenpay_store_name = result.get('storeName')
            self.ifthenpay_email_account = result.get('email')
            self.ifthenpay_gateway_key = result.get('gatewayKey')
            self.ifthenpay_expiry_days = result.get('expiryDays')
            self.url_base = base_url


            callback = '/payment/ifthenpay/s2s_callback?amount=[AMOUNT]&reference=[ORDER_ID]&apk=[ANTI_PHISHING_KEY]'
            payload = {
                'apKey': result.get('tokenApi'),
                'chave': result.get('gatewayKey'),
                'urlCb': base_url + callback
            }
            response = requests.post('https://api.ifthenpay.com/endpoint/callback/activation/?cms=odoo', json=payload, timeout=30)
            response.raise_for_status()
            api_response = response.json()
            _logger.info("ifthenpay: active callback %s", api_response)

        except Exception as e:
            _logger.error("Erro ao buscar resposta da API ifthenpay: %s", e)
            raise UserError(_("Error retrieving response from ifthenpay API: %s") % str(e))