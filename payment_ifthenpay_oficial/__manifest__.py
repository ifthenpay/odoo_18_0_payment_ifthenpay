{
    'name': "Payment Provider: ifthenpay gateway",
    'version': '18.0.0.0.1',
    'author': "ifthenpay",
    'sequence': 350,
    'category': 'Accounting/Payment Providers',
    'summary': 'The payment services by reference via MULTIBANCO, MB WAY, COFIDIS PAY, GOOGLE PAY, APPLE PAY, PIX, PAYSHOP, Credit Card provided by ifthenpay offer numerous advantages for your business.',
    'description': """
This module integrates ifthenpay's payment gateway into your Odoo store.

Data transmitted to ifthenpay includes customer name, contact info, order reference and payment amount for processing purposes.

For details, refer to our Privacy Policy: https://ifthenpay.com/politica-de-privacidade/
""",
    'website': "https://ifthenpay.com/",
    'depends': [
        'payment',
        'website',
        'website_sale',
        'account',
        'account_payment',
    ],
    'data': [
        'views/payment_form_templates.xml',
        'views/payment_provider_views.xml',
        'views/payment_method_templates.xml',
        'views/payment_completed.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_ifthenpay_oficial/static/src/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'application': True,
    'installable': True,
    'license': 'OPL-1',
}