{
    'name': "ifthenpay gateway",
    'version': '0.0.1',
    'author': "ifthenpay",
    'sequence': 350,
    'category': 'Accounting/Payment Providers',
    'summary': 'The payment services by reference via MULTIBANCO, MB WAY, PAYSHOP, and Credit Card provided by ifthenpay offer numerous advantages for your business.',
    'description': """
Modern and efficient solution for integrating payment methods
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
    # 'post_init_hook': 'post_init_hook',
    # 'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {
        'web.assets_frontend': [
            'payment_ifthenpay/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}