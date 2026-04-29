{
    'name': 'Gestión de Sorteos (Rifas)',
    'version': '18.0.6.0.0',
    'category': 'Sales',
    'summary': 'Gestión de sorteos mediante venta de tickets sobre productos con stock',
    'description': """
        Módulo ADDOMS para gestionar sorteos (rifas) en Odoo 18 Community.
        Permite seleccionar productos con stock, generar tickets numerados,
        venderlos vía tienda virtual y ejecutar sorteos aleatorios.
    """,
    'author': 'ADDOMS',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'sale_stock',
        'website_sale',
        'mail',
        'portal',
        'payment_custom',
        'auth_signup',
    ],
    'data': [
        # Security
        'security/raffle_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/raffle_sequence.xml',
        'data/raffle_data.xml',
        'data/cron_data.xml',
        'data/mail_template_data.xml',
        # Views
        'views/raffle_views.xml',
        'views/raffle_ticket_views.xml',
        'views/product_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/whatsapp_message_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        # Templates frontend
        'views/templates/raffle_ticket_grid.xml',
        'views/templates/raffle_cart.xml',
        'views/templates/raffle_portal.xml',
        'views/templates/raffle_winners.xml',
        'views/templates/auth_signup.xml',
        # Wizards
        'wizard/raffle_draw_wizard.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'raffle_management/static/src/scss/raffle_ticket_grid.scss',
            'raffle_management/static/src/js/raffle_ticket_grid.js',
            'raffle_management/static/src/js/raffle_cart_countdown.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
