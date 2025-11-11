/** @odoo-module **/

import { rpc, RPCError } from "@web/core/network/rpc";
import paymentForm from '@payment/js/payment_form';
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';

paymentForm.include({
    _ifthenpayModal: null,
    _ifthenpayIframe: null,
    _ifthenpayLoadingModal: null,
    _isIfthenpaySelected: false,
    _currentIfthenpayTxRef: null,

    /**
     * @override
     * Inicializa o widget e configura os listeners para o modal e iframe.
     */
    start: async function () {
        const _superResult = await this._super.apply(this, arguments);

        this._ifthenpayModal = document.querySelector('#ifthenpay_modal');
        this._ifthenpayIframe = document.querySelector('#ifthenpay_iframe');
        this._ifthenpayLoadingModal = document.querySelector('#ifthenpay_loading_modal');

        if (!this._ifthenpayModal || !this._ifthenpayIframe || !this._ifthenpayLoadingModal) {
            console.error("ifthenpay: CRITICO! Elementos do modal NAO encontrados. Verifique se o template 'ifthenpay_checkout_modal' esta carregado globalmente no HTML.");
            return _superResult;
        }

        this._ifthenpayModal = $(this._ifthenpayModal).modal({ show: false, backdrop: 'static', keyboard: false });

        this._ifthenpayIframe.style.display = 'none';
        this._ifthenpayLoadingModal.classList.add('d-none');

        this._ifthenpayModal.on('hidden.bs.modal', async () => {
            this._ifthenpayIframe.src = '';
            this._ifthenpayLoadingModal.classList.add('d-none');
            this._ifthenpayIframe.style.display = 'none';
            
            this._enableButton(true); 
            if (this._currentIfthenpayTxRef) {
                try {
                    const statusCheckResponse = await rpc('/payment/ifthenpay/check_transaction_status', {
                        tx_reference: this._currentIfthenpayTxRef,
                    });

                    if (statusCheckResponse && (statusCheckResponse.status === 'success' || statusCheckResponse.status === 'pending')) {
                        window.location.href = '/shop/payment/validate';
                    } else if (statusCheckResponse && statusCheckResponse.status === 'error') {
                        this._displayErrorDialog(_t("Payment Failed"), _t("The payment was not completed successfully."));
                    } else {
                         console.warn(`ifthenpay: Status desconhecido.`);
                    }
                } catch (error) {
                    console.error("ifthenpay: Erro ao verificar status da transacao apos fechar modal:", error);
                } finally {
                    this._currentIfthenpayTxRef = null;
                }
            }
        });


        this._ifthenpayIframe.addEventListener('load', () => {
            this._ifthenpayLoadingModal.classList.add('d-none');
            this._ifthenpayIframe.style.display = 'block';

            this._enableButton(true); 
        });

        window.addEventListener('message', this._onIframeMessage.bind(this), false);
        
        this.el.addEventListener('change', (ev) => {
            if (ev.target.name === 'o_payment_radio') {
                const selectedProviderCode = ev.target.dataset.providerCode;
                this._isIfthenpaySelected = (selectedProviderCode === 'ifthenpay');
            }
        });

        return _superResult;
    },

    /**
     * @override
     * Lida com a submissao do formulario de pagamento.
     * Permitimos que o _super execute para que o Odoo lide com o bloqueio da UI inicial
     * e a passagem de argumentos para o backend.
     */
    _submitForm: async function () {
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        const providerCode = checkedRadio ? checkedRadio.dataset.providerCode : null;

        if (providerCode === 'ifthenpay') {
            return this._super(...arguments); 
        } else {
            return this._super(...arguments);
        }
    },

    /**
     * @override
     * Processa o fluxo de redirecionamento para ifthenpay.
     */
    _processRedirectFlow: async function (providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'ifthenpay') {
            return this._super(...arguments);
        }

        if (!this._ifthenpayModal || !this._ifthenpayIframe || !this._ifthenpayLoadingModal) {
            const errorMessage = _t("An internal error has occurred: the ifthenpay payment modal has not loaded correctly on the page.");
            this._displayErrorDialog(_t("Configuration Error"), errorMessage);
            this._enableButton(true); 
            return;
        }

        this._ifthenpayLoadingModal.classList.remove('d-none');
        this._ifthenpayIframe.style.display = 'none';
        this._ifthenpayModal.modal('show');

        try {
            this._currentIfthenpayTxRef = processingValues.reference;

            const response = await rpc('/payment/ifthenpay/submit_payment', {
                provider_id: this.paymentContext.providerId,
                tx_reference: this._currentIfthenpayTxRef,
                payment_method_code: paymentMethodCode,
            });

            if (response.error) {
                throw new Error(response.error);
            }

            if (response.redirect_url) {
                this._ifthenpayIframe.src = response.redirect_url;
            } else if (response.status) {
                this._ifthenpayModal.modal('hide');
                if (response.status === 'pending' || response.status === 'success') {
                    window.location.href = '/shop/payment/validate';
                } else {
                    this._displayErrorDialog(_t("Payment Failed"), response.message || _t("Unknown payment status."));
                    this._enableButton(true);
                }
                this._currentIfthenpayTxRef = null;
            } else {
                throw new Error("Resposta inesperada do servidor ifthenpay. Nenhuma redirect_url ou status valido.");
            }

        } catch (error) {
            console.error("ifthenpay: Erro ao processar o pagamento:", error);
            this._ifthenpayModal.modal('hide');
            this._displayErrorDialog(_t("Payment Failed"), error?.data?.message || error.message || _t("An error occurred while processing the payment with ifthenpay."));
            this._enableButton(true);
            this._currentIfthenpayTxRef = null;
        }
    },

    /**
     * @private
     */
    _onIframeMessage: function (event) {
        if (event.data && typeof event.data === 'object') {
            if (event.data.type === 'ifthenpay_loading_ready') {
                const params = event.data.params;
                const queryString = new URLSearchParams(params).toString();
                
                fetch(`/payment/ifthenpay/iframe_callback?${queryString}`)
                .then(result => {
                    this._ifthenpayModal.modal('hide');
                }).catch(error => {
                    this._ifthenpayModal.modal('hide');
                    this._displayErrorDialog(_t("Payment Failed"), _t("The payment with ifthenpay failed. Please try again."));
                    this._currentIfthenpayTxRef = null;
                });

            } else if (event.data.type === 'ifthenpay_payment_status') {
                const status = event.data.status;
                const message = event.data.message;

                if (status === 'success') {
                    this._ifthenpayModal.modal('hide');
                    window.location.href = '/shop/payment/validate';
                    this._currentIfthenpayTxRef = null;
                } else if (status === 'failed') {
                    this._ifthenpayModal.modal('hide');
                    this._displayErrorDialog(_t("Payment Failed"), message || _t("The payment with ifthenpay failed. Please try again."));
                    this._currentIfthenpayTxRef = null;
                } else if (status === 'pending') {
                    this._ifthenpayModal.modal('hide');
                    window.location.href = '/shop/payment/validate';
                    this._currentIfthenpayTxRef = null;
                } else if (status === 'closed') {
                    this._ifthenpayModal.modal('hide');
                    this._displayErrorDialog(_t("Payment Cancelled"), message || _t("The payment has been canceled. Please try again."));
                    this._currentIfthenpayTxRef = null;
                }
            }
        }
    },

    /**
     * @private
     */
    _displayErrorDialog: function (title, message) {
        this._super(title, message);
    },
});