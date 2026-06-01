from odoo import models
from odoo.tools.translate import _lt


class Website(models.Model):
    """Herencia de website para personalizar textos de botones del checkout."""
    _inherit = 'website'

    def _get_checkout_step_list(self):
        """Sobreescribe textos de botones del checkout:
        - Carrito: 'Checkout' → 'Ir a pagar'
        - Checkout/Dirección: 'Confirm' → 'Vamos a pagar'
        - Pago: 'Back to delivery' → 'Volver a la tienda' (apunta a /shop)
        """
        steps = super()._get_checkout_step_list()
        for xmlids, values in steps:
            if 'website_sale.cart' in xmlids:
                values['main_button'] = _lt("Ir a pagar")
            if 'website_sale.checkout' in xmlids:
                values['main_button'] = _lt("Vamos a pagar")
            if 'website_sale.payment' in xmlids:
                values['back_button'] = _lt("Volver a la tienda")
                values['back_button_href'] = '/shop'
        return steps
