import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class WhatsappMessage(models.Model):
    """Registro de mensajes WhatsApp enviados.
    Sirve como log para auditoría y debugging de notificaciones."""
    _name = 'whatsapp.message'
    _description = 'Mensaje WhatsApp'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner', string='Destinatario', required=True)
    phone_number = fields.Char(string='Número', required=True)
    message_type = fields.Selection([
        ('welcome', 'Bienvenida'),
        ('verification', 'Verificación 2FA'),
        ('ticket_purchase', 'Compra de Ticket'),
        ('winner', 'Ganador'),
        ('cancellation', 'Cancelación'),
    ], string='Tipo', required=True)
    body = fields.Text(string='Contenido')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('failed', 'Fallido'),
    ], string='Estado', default='draft')
    error_message = fields.Text(string='Error')
    raffle_id = fields.Many2one('raffle.raffle', string='Sorteo')
    ticket_id = fields.Many2one('raffle.ticket', string='Ticket')

    @api.model
    def send_whatsapp(self, partner, message_type, body, raffle=None, ticket=None):
        """Método central para enviar mensajes WhatsApp.
        Crea el registro de log y delega el envío al proveedor configurado.
        Si no hay proveedor configurado, solo registra el mensaje como 'enviado' (simulación)."""
        if not partner.whatsapp_number:
            _logger.warning('Partner %s no tiene número de WhatsApp', partner.name)
            return False

        msg = self.create({
            'partner_id': partner.id,
            'phone_number': partner.whatsapp_number,
            'message_type': message_type,
            'body': body,
            'raffle_id': raffle.id if raffle else False,
            'ticket_id': ticket.id if ticket else False,
        })

        provider = self.env['ir.config_parameter'].sudo().get_param(
            'raffle_management.whatsapp_provider', 'none'
        )

        if provider == 'twilio':
            msg._send_via_twilio()
        elif provider == 'meta':
            msg._send_via_meta()
        else:
            # Modo simulación: marcar como enviado sin enviar realmente
            msg.state = 'sent'
            _logger.info('WhatsApp [SIMULACIÓN] a %s: %s', partner.whatsapp_number, body)

        return msg

    def _send_via_twilio(self):
        """Envía mensaje vía Twilio WhatsApp API.
        Requiere: pip install twilio (o usar requests directo)."""
        self.ensure_one()
        try:
            account_sid = self.env['ir.config_parameter'].sudo().get_param(
                'raffle_management.whatsapp_account_sid')
            auth_token = self.env['ir.config_parameter'].sudo().get_param(
                'raffle_management.whatsapp_auth_token')
            from_number = self.env['ir.config_parameter'].sudo().get_param(
                'raffle_management.whatsapp_from_number')

            if not all([account_sid, auth_token, from_number]):
                raise Exception('Credenciales de Twilio incompletas')

            import requests
            response = requests.post(
                f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json',
                data={
                    'From': f'whatsapp:{from_number}',
                    'To': f'whatsapp:{self.phone_number}',
                    'Body': self.body,
                },
                auth=(account_sid, auth_token),
                timeout=30,
            )
            if response.status_code in (200, 201):
                self.state = 'sent'
            else:
                self.state = 'failed'
                self.error_message = response.text
                _logger.error('Twilio error: %s', response.text)

        except Exception as e:
            self.state = 'failed'
            self.error_message = str(e)
            _logger.error('Error enviando WhatsApp via Twilio: %s', e)

    def _send_via_meta(self):
        """Envía mensaje vía Meta Business WhatsApp API.
        Placeholder para implementación futura."""
        self.ensure_one()
        self.state = 'failed'
        self.error_message = 'Meta Business API no implementada aún'
        _logger.warning('Meta Business API no implementada')
