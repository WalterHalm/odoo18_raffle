from odoo import api, models

# Campos custom que se pasan del formulario y deben guardarse en el partner
_RAFFLE_PARTNER_FIELDS = ('whatsapp_number', 'dni_number', 'nickname')


class ResUsers(models.Model):
    """Herencia de res.users para guardar campos custom del registro
    (WhatsApp, DNI, nickname) en el partner durante el signup.
    También asigna país Perú, tipo de identificación DNI y dirección mínima."""
    _inherit = 'res.users'

    @api.model
    def _create_user_from_template(self, values):
        """Extrae campos custom antes de crear el usuario (no son campos de res.users).
        Después de crear el usuario, los guarda en el partner asociado
        junto con país Perú, tipo DNI y teléfono = WhatsApp."""
        raffle_data = {f: values.pop(f) for f in _RAFFLE_PARTNER_FIELDS if f in values}
        new_user = super()._create_user_from_template(values)
        if new_user.partner_id:
            partner_vals = dict(raffle_data)
            # Asignar país Perú
            peru = self.env.ref('base.pe', raise_if_not_found=False)
            if peru:
                partner_vals['country_id'] = peru.id
            # Asignar tipo de identificación DNI (solo si l10n_pe está instalado)
            if 'l10n_latam_identification_type_id' in self.env['res.partner']._fields:
                dni_type = self.env.ref(
                    'l10n_pe.it_DNI', raise_if_not_found=False
                ) or self.env['l10n_latam.identification.type'].search(
                    [('name', 'ilike', 'DNI')], limit=1
                )
                if dni_type:
                    partner_vals['l10n_latam_identification_type_id'] = dni_type.id
            # Teléfono = WhatsApp (para cumplir campo obligatorio de facturación)
            if raffle_data.get('whatsapp_number'):
                partner_vals['phone'] = raffle_data['whatsapp_number']
            if partner_vals:
                new_user.partner_id.write(partner_vals)
        return new_user
