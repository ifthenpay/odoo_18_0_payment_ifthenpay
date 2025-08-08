# -*- coding: utf-8 -*-
import logging
import werkzeug # Para redirecionamentos
from werkzeug.exceptions import BadRequest
from odoo import http
from odoo.http import request
import requests
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

class IfthenpayController(http.Controller):

    @http.route('/payment/ifthenpay/submit_payment', type='json', auth='public', csrf=False, website=True)
    def submit_payment(self, provider_id, method_code=None, tx_reference=None, extra_data=None):
        
        provider = request.env['payment.provider'].sudo().browse(int(provider_id))

        if not provider or provider.code != 'ifthenpay':
            _logger.error("ifthenpay: Provedor de pagamento invalido ou nao ifthenpay: %s", provider_id)
            return {'error': 'Provedor de pagamento invalido.'}

        tx_reference = extra_data.get('reference') if extra_data else tx_reference
        method_code = extra_data.get('method') if extra_data else method_code

        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', tx_reference),
            ('provider_code', '=', 'ifthenpay')
        ], limit=1)

        if not tx:
            _logger.error("ifthenpay: Transacao nao encontrada para referencia %s", tx_reference)
            return {'error': 'Transacao nao encontrada.'}

        if method_code == 'ifthenpay' or not method_code:
            _logger.info("ifthenpay: Iniciando fluxo de checkout externo para tx %s", tx_reference)
            try:
                api_response = provider._ifthenpay_api_create_payment_pinpay(tx)
                redirect_url = api_response.get('payment_url')

                if not redirect_url:
                    raise Exception("URL de pagamento nao retornada pela ifthenpay.")

                return {'redirect_url': redirect_url}
            except Exception as e:
                _logger.exception("ifthenpay: Erro ao obter URL de pagamento externo para tx %s: %s", tx_reference, e)
                return {'error': str(e)}
        else:
            _logger.warning("ifthenpay: Metodo de pagamento nao suportado: %s", method_code)
            return {'error': 'Metodo de pagamento nao suportado.'}
    
    @http.route('/payment/ifthenpay/get_payment_methods_icons', type='json', auth='public', website=True)
    def ifthenpay_get_payment_methods_icons(self):
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'ifthenpay')], limit=1)

        if not provider or not provider.ifthenpay_api_key:
            _logger.warning("NOT PROVIDER")
            return {'error': 'API Key for ifthenpay not configured.'}

        integration = provider._get_integration_api(provider.ifthenpay_api_key)
        if integration is None:
            _logger.warning("NONE INTEGRATION")
            return  {'error': 'Provider disable.'}
        
        url = f'https://api.ifthenpay.com/gateway/methods/available'

        accounts = integration.get('accountKeys')

        cleaned_lines = []
        for part in accounts.split(";"):
            cleaned_lines.append(part.strip()) 

        entidades = [item.split("|")[0] for item in cleaned_lines]
        entidades = [e.upper() for e in entidades]
        tem_numerico = any(e.isdigit() for e in entidades)

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                data_filter = [
                    m for m in data
                    if m.get("Entity", "").upper() in entidades
                    or (tem_numerico and m.get("Entity", "").upper() == "MB")
                ]
                return {'success': True, 'data': data_filter}
            else:
                return {'error': 'Invalid API response from ifthenpay.', 'details': data}

        except requests.exceptions.RequestException as e:
            return {'error': f'Failed to connect to ifthenpay API: {e}'}
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON response from ifthenpay API.'}

    # NOVA ROTA: Para a ifthenpay enviar o status de volta para o Odoo (Webhook / Notificacao)
    @http.route('/payment/ifthenpay/s2s_callback', type='http', auth='public', website=True, csrf=False)
    def ifthenpay_s2s_callback(self, **get_params):
        _logger.info("ifthenpay_s2s_callback recebido (dados): %s", get_params)

        try:
            request.env['payment.transaction'].sudo()._handle_notification_data('ifthenpay', get_params)
            return "OK"

        except Exception as e:
            _logger.exception("ifthenpay_s2s_callback: Erro ao processar notificacao de pagamento: %s", e)
            raise BadRequest("Error: Internal server error")

    @http.route('/payment/ifthenpay/check_transaction_status', type='json', auth='public', website=True, csrf=False)
    def ifthenpay_check_transaction_status(self, tx_reference, **kwargs):
        _logger.info("ifthenpay_check_transaction_status chamado para: %s", tx_reference)
        tx = request.env['payment.transaction'].sudo().search([('reference', '=', tx_reference)], limit=1)
        
        if not tx:
            _logger.warning("ifthenpay_check_transaction_status: Transacao Odoo nao encontrada para referencia %s.", tx_reference)
            return {'status': 'error', 'message': 'Transaction not found.'}

        if tx.state == 'done':
            return {'status': 'success'}
        elif tx.state == 'pending':
            return {'status': 'pending'}
        elif tx.state == 'cancel':
            return {'status': 'error', 'message': 'Pagamento cancelado.'}
        elif tx.state == 'error':
            return {'status': 'error', 'message': 'Erro no pagamento.'}
        else: # draft, authorized, etc. - assume que não foi concluído ainda
            return {'status': 'processing', 'message': 'Aguardando confirmacao do pagamento.'}

    @http.route('/payment/ifthenpay/iframe_callback', type='http', auth='public', website=True, csrf=False)
    def ifthenpay_iframe_callback(self, **get_params):
        _logger.info("ifthenpay_iframe_callback recebido (dados): %s", get_params)

        odoo_tx_reference = get_params.get('reference')
        odoo_amount = get_params.get('amount')
        return_status = get_params.get('status')

        if return_status == 'cancel':
            return request.render('payment_ifthenpay.ifthenpay_iframe_post_message_template', {
                'payment_status': 'closed',
                'message': _('The payment has been canceled or the window has been closed. You can try again.')
            })

        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', odoo_tx_reference),
            ('amount', '=', odoo_amount),
            ('provider_code', '=', 'ifthenpay')
        ], limit=1)

        if not tx:
            _logger.error("ifthenpay_iframe_callback: Transação Odoo ou token invalido para referencia %s.", odoo_tx_reference)
            return request.render(
                'payment_ifthenpay.ifthenpay_iframe_error_template', 
                {'message': _('Invalid or expired transaction.'), 'title': _('An error occurred while processing the payment:')}
            )

        provider = tx.provider_id
        if not provider:
            _logger.error("ifthenpay_iframe_callback: Provedor de pagamento nao encontrado para a transacao %s.", tx.reference)
            return request.render(
                'payment_ifthenpay.ifthenpay_iframe_error_template', 
                {'message': _('Payment provider configuration error.'), 'title': _('An error occurred while processing the payment:')}
            )
        
        if return_status == 'error':
            _logger.warning("ifthenpay: Redirecionamento de ERRO recebido para transacao %s.", tx.reference)
            if tx.state not in ('cancel', 'error'): # Evita sobrescrever um estado final de 'cancel' ou 'error'
                tx._set_error(state_message=_('An error occurred while trying to process the payment with ifthenpay. Please try again.'))
            tx._invalidate_cache()
            return request.render('payment_ifthenpay.ifthenpay_iframe_post_message_template', {
                'payment_status': 'failed',
                'message': tx.state_message or _("There was an error in the payment."),
            })

        if tx.state == 'draft':
            tx._set_pending(state_message=_('Payment initiated with ifthenpay, awaiting confirmation.'))

        payment_status = 'pending'
        message = 'Your payment is being processed and awaiting confirmation. Please wait.'

        if tx.state == 'done':
            payment_status = 'success'
            message = 'Pagamento realizado com sucesso!'
        elif tx.state == 'cancel' or tx.state == 'error':
            payment_status = 'failed'
            message = tx.state_message or 'O pagamento falhou ou foi cancelado.'

        return request.render('payment_ifthenpay.ifthenpay_iframe_post_message_template', {
            'payment_status': payment_status,
            'message': message,
        })