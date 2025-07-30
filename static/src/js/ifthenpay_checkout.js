/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { _t } from '@web/core/l10n/translation';
import { rpc } from '@web/core/network/rpc';
import { notificationService } from '@web/core/notifications/notification_service';

const IfThenPayCheckoutWidget = publicWidget.Widget.extend({
    services: [
        'notification',
    ],

    selector: '.o_payment_form',

    events: {
        'change input[name="o_payment_radio"]': '_onPaymentMethodChange',
    },

    /**
     * @override
     */
    start: async function () {
        await this._super(...arguments);

        const $ifthenpayRadioInput = this.$('input[data-payment-method-code="ifthenpay"]');

        if ($ifthenpayRadioInput.length > 0) {
            const $ifthenpayListItem = $ifthenpayRadioInput.closest("li[name='o_payment_option']");
            const $dynamicIconsContainer = $ifthenpayListItem.find('.ifthenpay-dynamic-icons');
            const $defaultIconSpan = $ifthenpayListItem.find("span.shadow-sm");

            if ($defaultIconSpan.length > 0 && $defaultIconSpan.find("img[src*='/web/image/payment.method/'][src*='/image_payment_form/'], img[src*='ifthenpay.png']").length === 0) {
                $defaultIconSpan = $();
            }

            if ($defaultIconSpan.length === 0) {
                $defaultIconSpan = $ifthenpayListItem.find("span[data-bs-toggle='tooltip'][aria-label='ifthenpay']");
            }

            if ($defaultIconSpan.length === 0) {
                $defaultIconSpan = $ifthenpayListItem.find("span[data-oe-expression*='logo_pm_sudo.image_payment_form']");
            }

            if ($dynamicIconsContainer.length > 0) {
                if ($defaultIconSpan.length > 0) {
                    $defaultIconSpan.empty();
                    $defaultIconSpan.append($dynamicIconsContainer);
                } else {
                    console.warn("ifthenpay: Span do ícone padrão não encontrado. Anexando ícones dinâmicos diretamente ao item da lista de pagamento.");
                    $ifthenpayListItem.append($dynamicIconsContainer);
                }
                
                $dynamicIconsContainer.show();
                await this._fetchAndDisplayIcons($dynamicIconsContainer);

            } else {
                console.warn("ifthenpay: Não foi possível encontrar o container de ícones dinâmicos IfThenPay dentro do item da lista de pagamento.");
            }
        } else {
            console.log("ifthenpay payment method não encontrado na página (pode não estar ativo ou não nesta vista).");
        }

        this._handleIfThenPayVisibility(); 
    },

    _onPaymentMethodChange: function (ev) {
        this._handleIfThenPayVisibility();
    },

    _handleIfThenPayVisibility: function() {
        const $checkedRadio = this.$('input[name="o_payment_radio"]:checked');
        const $ifthenpayProviderContainer = this.$('.o_payment_provider[data-provider-code="ifthenpay"]');

        if ($ifthenpayProviderContainer.length === 0) {
            console.warn("ifthenpay provider container (formulário inline) não encontrado para manipulação de visibilidade.");
            return;
        }

        const providerCode = $checkedRadio.data('providerCode');
        const paymentMethodCode = $checkedRadio.data('paymentMethodCode');

        if (providerCode === 'ifthenpay' || paymentMethodCode === 'ifthenpay') {
            $ifthenpayProviderContainer.show();
        } else {
            $ifthenpayProviderContainer.hide();
        }
    },

    /**
     * Busca os ícones de pagamento do backend e os exibe no container fornecido.
     * @param {jQuery} targetContainer O elemento jQuery onde os ícones devem ser injetados.
     */
    _fetchAndDisplayIcons: async function(targetContainer) {
        console.log('tentando buscar imgs: _fetchAndDisplayIcons')
        if (!targetContainer || targetContainer.length === 0) {
            console.error("Nenhum container alvo válido fornecido para _fetchAndDisplayIcons.");
            return;
        }

        try {
            const result = await rpc('/payment/ifthenpay/get_payment_methods_icons', { 
                params: {},
            });
            console.log('retorno de result: ' + result)

            if (result.error) {
                console.error('ifthenpay API Error from Backend:', result.error);
                this.notification.add(_t("ifthenpay: Failed to load payment methods. Please try again later."), { 
                    type: 'danger',
                    sticky: false,
                });
                return;
            }

            const data = result.data;
            console.log("RPC Result:", result);

            if (!Array.isArray(data) || data.length === 0) {
                console.warn('ifthenpay: Resposta da API inválida do backend ou sem dados para ícones.');
                targetContainer.html('<p class="text-muted small mb-0">Nenhum método de pagamento disponível.</p>');
                return;
            }

            targetContainer.empty();
            data.forEach(method => {
                const img = $('<img>', {
                    src: method.SmallImageUrl,
                    alt: method.Method,
                    style: 'height: 30px; margin-right: 6px;',
                });
                targetContainer.append(img);
            });
        } catch (err) {
            console.error('ifthenpay: Falha ao buscar ícones via chamada de backend', err);
            this.notification.add(_t("ifthenpay: An unexpected error occurred while loading payment methods."), { 
                type: 'danger',
                sticky: false,
            });
        }
    }
});

publicWidget.registry.IfThenPayCheckout = IfThenPayCheckoutWidget;