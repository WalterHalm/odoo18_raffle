from odoo import models
from odoo.tools.translate import _lt


class Website(models.Model):
    """Herencia de website para personalizar textos de botones del checkout."""
    _inherit = 'website'

    def _get_checkout_step_list(self):
        """Sobreescribe textos y destinos de botones del checkout:
        - Carrito: 'Ir a pagar' apunta a /shop/raffle/confirm_order (confirma directo)
        - Pago: 'Volver a la tienda' apunta a /shop
        """
        steps = super()._get_checkout_step_list()
        for xmlids, values in steps:
            if 'website_sale.cart' in xmlids:
                values['main_button'] = _lt("Ir a pagar")
                values['main_button_href'] = '/shop/raffle/confirm_order'
            if 'website_sale.payment' in xmlids:
                values['back_button'] = _lt("Volver a la tienda")
                values['back_button_href'] = '/shop'
        return steps
