from odoo import _, api, fields, models


class ResPartner(models.Model):
    """Herencia de res.partner para agregar campos requeridos por el sistema de rifas.
    Requerimiento del cliente:
    - WhatsApp obligatorio (identificador de usuario)
    - DNI obligatorio (Perú)
    - Nickname opcional (si vacío se muestra 'Usuario XXXX')"""
    _inherit = 'res.partner'

    whatsapp_number = fields.Char(
        string='WhatsApp',
        help='Número de WhatsApp del participante. Obligatorio para registro web.',
    )
    dni_number = fields.Char(
        string='DNI',
        help='Documento Nacional de Identidad (Perú). Obligatorio para registro web.',
    )
    nickname = fields.Char(
        string='Nickname',
        help='Apodo público del participante. Si está vacío se muestra "Usuario XXXX".',
    )
    display_nickname = fields.Char(
        string='Nombre Público',
        compute='_compute_display_nickname',
    )
    whatsapp_verified = fields.Boolean(
        string='WhatsApp Verificado',
        default=False,
    )

    @api.depends('nickname', 'name')
    def _compute_display_nickname(self):
        """Muestra el nickname si existe, sino el nombre del partner."""
        for rec in self:
            rec.display_nickname = rec.nickname or rec.name or _('Anónimo')
