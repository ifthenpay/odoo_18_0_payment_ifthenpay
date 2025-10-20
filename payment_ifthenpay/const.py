# Part of Odoo. See LICENSE file for full copyright and licensing details.

SUPPORTED_CURRENCIES = (
    'EUR',
)

DEFAULT_PAYMENT_METHOD_CODES = {
    # Primary payment methods.
    'ifthenpay',
}

PAYMENT_STATUS_MAPPING = {
    'pending': (
        'PENDING',
        'CREATED',
        'APPROVED',  # The buyer approved a checkout order.
    ),
    'done': (
        'COMPLETED',
        'CAPTURED',
    ),
    'cancel': (
        'DECLINED',
        'DENIED',
        'VOIDED',
    ),
    'error': ('FAILED',),
}

# Events which are handled by the webhook.
HANDLED_WEBHOOK_EVENTS = [
    'CHECKOUT.ORDER.COMPLETED',
    'CHECKOUT.ORDER.APPROVED',
    'CHECKOUT.PAYMENT-APPROVAL.REVERSED',
]
