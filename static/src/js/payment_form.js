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
            console.error("ifthenpay: CRÍTICO! Elementos do modal NÃO encontrados. Verifique se o template 'ifthenpay_checkout_modal' está carregado globalmente no HTML.");
            return _superResult;
        }

        // Inicializa o modal do Bootstrap
        this._ifthenpayModal = $(this._ifthenpayModal).modal({ show: false, backdrop: 'static', keyboard: false });

        // Garante que o iframe e o spinner estejam escondidos inicialmente
        this._ifthenpayIframe.style.display = 'none';
        this._ifthenpayLoadingModal.classList.add('d-none');

        // Adiciona um listener para quando o modal for completamente escondido
        // Usamos 'this' diretamente, pois o contexto é mantido por jQuery/Bootstrap para eventos.
        this._ifthenpayModal.on('hidden.bs.modal', async () => {
            console.log("ifthenpay: Modal fechado.");
            this._ifthenpayIframe.src = ''; // Limpa a URL do iframe
            this._ifthenpayLoadingModal.classList.add('d-none'); // Esconde o spinner
            this._ifthenpayIframe.style.display = 'none'; // Esconde o iframe
            
            this._enableButton(true); 
            // verificar o status do pagamento após o modal ser fechado (manual ou via JS)
            if (this._currentIfthenpayTxRef) {
                console.log(`ifthenpay: Verificando status da transação ${this._currentIfthenpayTxRef} após fechamento do modal.`);
                try {
                    const statusCheckResponse = await rpc('/payment/ifthenpay/check_transaction_status', {
                        tx_reference: this._currentIfthenpayTxRef,
                    });

                    if (statusCheckResponse && (statusCheckResponse.status === 'success' || statusCheckResponse.status === 'pending')) {
                        console.log(`ifthenpay: Transação ${this._currentIfthenpayTxRef} confirmada como ${statusCheckResponse.status}. Redirecionando...`);
                        window.location.href = '/shop/payment/validate';
                    } else if (statusCheckResponse && statusCheckResponse.status === 'error') {
                        this._displayErrorDialog(_t("Payment Failed"), _t("The payment was not completed successfully."));
                    } else {
                         console.warn(`ifthenpay: Status desconhecido.`);
                         // Se o status for desconhecido (ex: 'draft' ainda), o usuário permanece na página de checkout.
                    }
                } catch (error) {
                    console.error("ifthenpay: Erro ao verificar status da transação após fechar modal:", error);
                    // Opcional: Mostrar um erro genérico
                } finally {
                    this._currentIfthenpayTxRef = null; // Limpa a referência após a verificação
                }
            }
        });

        // Adiciona um listener para quando o conteúdo do iframe terminar de carregar
        // Usamos uma arrow function para manter o contexto 'this'
        this._ifthenpayIframe.addEventListener('load', () => {
            this._ifthenpayLoadingModal.classList.add('d-none');
            console.log("Ifthenpay: iframe carregado.");
            this._ifthenpayIframe.style.display = 'block';

            // NOVO: Desbloqueia a UI do Odoo *APÓS* o iframe carregar e o modal aparecer.
            // Isso garante que o bloqueio do Odoo seja removido quando o usuário puder interagir com o iframe.
            this._enableButton(true); 
        });

        // O listener de 'message' já está bindado corretamente
        window.addEventListener('message', this._onIframeMessage.bind(this), false);
        
        // Listener para mudança de seleção de método de pagamento
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
     * Lida com a submissão do formulário de pagamento.
     * Permitimos que o _super execute para que o Odoo lide com o bloqueio da UI inicial
     * e a passagem de argumentos para o backend.
     */
    _submitForm: async function () {
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        const providerCode = checkedRadio ? checkedRadio.dataset.providerCode : null;

        if (providerCode === 'ifthenpay') {
            console.log("Ifthenpay: Iniciando submissão para Ifthenpay. Permitindo bloqueio temporário da UI do Odoo.");
            // Permitimos que o _super execute, ele irá bloquear a UI e chamar _initiatePaymentFlow
            return this._super(...arguments); 
        } else {
            // Para outros provedores, permite que o método pai _submitForm execute normalmente.
            return this._super(...arguments);
        }
    },

    /**
     * @override
     * Processa o fluxo de redirecionamento para ifthenpay.
     */
    _processRedirectFlow: async function (providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        console.log("ifthenpay: _processRedirectFlow CHAMADO para:", providerCode);

        if (providerCode !== 'ifthenpay') {
            return this._super(...arguments);
        }

        if (!this._ifthenpayModal || !this._ifthenpayIframe || !this._ifthenpayLoadingModal) {
            const errorMessage = _t("An internal error has occurred: the ifthenpay payment modal has not loaded correctly on the page.");
            this._displayErrorDialog(_t("Configuration Error"), errorMessage);
            // Em caso de erro crítico, reabilita o botão e a UI do Odoo.
            this._enableButton(true); 
            return;
        }

        // Mostra nosso spinner personalizado e esconde o iframe
        this._ifthenpayLoadingModal.classList.remove('d-none');
        this._ifthenpayIframe.style.display = 'none';
        this._ifthenpayModal.modal('show'); // Exibe o modal

        try {
            this._currentIfthenpayTxRef = processingValues.reference;

            // Aqui, a UI do Odoo ainda estará bloqueada pelo _submitForm.
            // O desbloqueio acontecerá no listener do iframe 'load' ou no fechamento do modal.
            const response = await rpc('/payment/ifthenpay/submit_payment', {
                provider_id: this.paymentContext.providerId,
                tx_reference: this._currentIfthenpayTxRef,
                payment_method_code: paymentMethodCode,
            });

            if (response.error) {
                throw new Error(response.error);
            }

            if (response.redirect_url) {
                console.log("Ifthenpay: URL de Redirecionamento obtida:", response.redirect_url);
                this._ifthenpayIframe.src = response.redirect_url;
                // O listener do iframe 'load' agora cuidará do desbloqueio da UI do Odoo.
            } else if (response.status) {
                // Se o backend retornar um status (para pagamentos diretos como MBWAY, Multibanco sem iframe)
                this._ifthenpayModal.modal('hide');
                if (response.status === 'pending' || response.status === 'success') {
                    window.location.href = '/shop/payment/validate';
                } else {
                    this._displayErrorDialog(_t("Payment Failed"), response.message || _t("Unknown payment status."));
                    this._enableButton(true); // Garante que a UI seja desbloqueada após o erro.
                }
                this._currentIfthenpayTxRef = null; // Limpa a referência se o modal fechar aqui
            } else {
                throw new Error("Resposta inesperada do servidor Ifthenpay. Nenhuma redirect_url ou status válido.");
            }

        } catch (error) {
            console.error("Ifthenpay: Erro ao processar o pagamento:", error);
            this._ifthenpayModal.modal('hide'); // Esconde o modal em caso de erro
            this._displayErrorDialog(_t("Payment Failed"), error?.data?.message || error.message || _t("An error occurred while processing the payment with Ifthenpay."));
            this._enableButton(true); // Garante que a UI seja desbloqueada após o erro.
            this._currentIfthenpayTxRef = null;
        }
    },

    /**
     * @private
     */
    _onIframeMessage: function (event) {
        if (event.data && typeof event.data === 'object' && event.data.type === 'ifthenpay_payment_status') {
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
    },

    /**
     * @private
     */
    _displayErrorDialog: function (title, message) {
        this._super(title, message);
    },
});