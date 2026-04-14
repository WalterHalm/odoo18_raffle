from odoo import _
from odoo.exceptions import UserError
from odoo.addons.web.controllers.home import SIGN_UP_REQUEST_PARAMS
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

# Registrar campos custom para que get_auth_signup_qcontext los preserve
SIGN_UP_REQUEST_PARAMS.update({'whatsapp_number', 'dni_number', 'nickname'})


class AuthSignupHome(AuthSignupHome):
    """Extensión mínima: solo valida campos custom y setea contraseña = DNI."""

    def _prepare_signup_values(self, qcontext):
        """Valida WhatsApp/DNI y setea contraseña = DNI antes del signup."""
        dni = qcontext.get('dni_number', '').strip()
        whatsapp = qcontext.get('whatsapp_number', '').strip()

        if not whatsapp:
            raise UserError(_('El número de WhatsApp es obligatorio.'))
        if not dni:
            raise UserError(_('El DNI es obligatorio.'))

        # Contraseña por defecto = DNI
        if not qcontext.get('password'):
            qcontext['password'] = dni
            qcontext['confirm_password'] = dni

        values = super()._prepare_signup_values(qcontext)

        # Pasar campos custom para que _create_user_from_template los guarde
        if whatsapp:
            values['whatsapp_number'] = whatsapp
        if dni:
            values['dni_number'] = dni
        nickname = qcontext.get('nickname', '').strip()
        if nickname:
            values['nickname'] = nickname

        return values
