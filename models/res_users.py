from odoo import api, models

# Campos custom que se pasan del formulario y deben guardarse en el partner
_RAFFLE_PARTNER_FIELDS = ('whatsapp_number', 'dni_number', 'nickname')


class ResUsers(models.Model):
    """Herencia de res.users para guardar campos custom del registro
    (WhatsApp, DNI, nickname) en el partner durante el signup."""
    _inherit = 'res.users'

    @api.model
    def _create_user_from_template(self, values):
        """Extrae campos custom antes de crear el usuario (no son campos de res.users).
        Después de crear el usuario, los guarda en el partner asociado."""
        raffle_data = {f: values.pop(f) for f in _RAFFLE_PARTNER_FIELDS if f in values}
        new_user = super()._create_user_from_template(values)
        if raffle_data and new_user.partner_id:
            new_user.partner_id.write(raffle_data)
        return new_user
