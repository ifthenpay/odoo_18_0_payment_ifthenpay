# -*- coding: utf-8 -*-
import requests
import time
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of `payment` to find the transaction based on ifthenpay notification data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction found.
        :rtype: recordset of `payment.transaction`
        :raise: `werkzeug.exceptions.BadRequest` if the data match no transaction.
        :raise: `werkzeug.exceptions.BadRequest` if the data match multiple transactions.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'ifthenpay':
            return tx

        reference = notification_data.get('reference')
        amount = float(notification_data.get('amount', 0.0))

        if not reference:
            _logger.error("ifthenpay: Missing reference in notification data: %s", notification_data)
            raise UserError(_("Missing reference in payment notification data."))

        tx = self.sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'ifthenpay'),
            ('amount', '=', amount),
        ], limit=1)

        if not tx:
            _logger.error("ifthenpay: Transaction not found for reference %s and amount %s.", 
                          reference, amount)
            raise UserError(_("Payment transaction not found or invalid."))

        return tx

    def _process_notification_data(self, notification_data):
        """ Override of `payment` to process the transaction based on ifthenpay notification data.

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise: `werkzeug.exceptions.ValidationError` if the data match no transaction.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'ifthenpay':
            return

        ifthenpay_payment_amount = float(notification_data.get('amount', 0.0))
        token = notification_data.get('apk')
        
        if token != self.provider_id.sudo().ifthenpay_api_key:
                _logger.warning("ifthenpay_s2s_callback: Token recebido (%s) NAO CORRESPONDE a API Key configurada para a transacao %s. POSSIVEL TENTATIVA DE FRAUDE.",
                            token, self.reference)
                self._set_error(_("Error: Invalid Token"))
                return

        if abs(ifthenpay_payment_amount - self.amount) > 0.001:
            _logger.warning("ifthenpay: Amount mismatch for transaction %s.", self.reference)
            self._set_error(_("Amount mismatch from ifthenpay notification."))
            return

        reference = notification_data.get('reference')
        self.provider_reference = f"ifthenpay_{reference}" 

        self._set_done()

        if 'inv' in reference.lower():
            _logger.info("ifthenpay: Transaction invoice %s processed", self.reference)
            self._create_payment()

        _logger.info("ifthenpay: Transaction %s processed. New state: %s", self.reference, self.state)

    def _ifthenpay_poll_status(self, tx_id_ifthen, max_attempts=10, wait_seconds=1):
        url = f'https://api.ifthenpay.com/gateway/transaction/status/get?transactionId={tx_id_ifthen}'

        attempts = 0
        while attempts < max_attempts:
            try:
                response = requests.get(url, timeout=30)

                if response.status_code == 404:
                    _logger.info("Tentativa %s/%s: transacao ainda nao encontrada (404).", attempts + 1, max_attempts)
                    attempts += 1
                    time.sleep(wait_seconds)
                    continue

                if response.status_code == 200:
                    return response.json()

                _logger.warning("Resposta inesperada %s para transacao %s", response.status_code, tx_id_ifthen)
                return None

            except requests.exceptions.RequestException as e:
                _logger.error("Erro na requisicao ao ifthenpay: %s", e)
                return None

        return None
