from datetime import timedelta

from odoo import _, api, fields, models
from markupsafe import Markup


class RaffleTicket(models.Model):
    """Ticket numerado de un sorteo.
    Cada sorteo genera N tickets con numeros secuenciales.
    El cliente puede seleccionar su numero favorito en la cuadricula.
    """
    _name = 'raffle.ticket'
    _description = 'Ticket de Sorteo'
    _order = 'number asc'
    _rec_name = 'name'

    name = fields.Char(string='Codigo', required=True, index=True)
    raffle_id = fields.Many2one(
        'raffle.raffle',
        string='Sorteo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    number = fields.Integer(string='Numero', required=True, index=True)
    state = fields.Selection([
        ('available', 'Disponible'),
        ('reserved', 'Reservado'),
        ('sold', 'Vendido'),
        ('cancelled', 'Cancelado'),
        ('winner', 'Ganador'),
    ], string='Estado', default='available', required=True, index=True)

    # --- Datos de reserva ---

    reservation_partner_id = fields.Many2one('res.partner', string='Reservado por')
    reservation_expiry = fields.Datetime(string='Expira Reserva')

    # --- Datos de compra ---

    partner_id = fields.Many2one('res.partner', string='Comprador')
    sale_order_line_id = fields.Many2one('sale.order.line', string='Linea de Venta')
    purchase_date = fields.Datetime(string='Fecha de Compra')
    cancellation_deadline = fields.Datetime(
        string='Limite de Cancelacion',
        compute='_compute_cancellation_deadline',
        store=True,
    )
    can_cancel = fields.Boolean(
        string='Puede Cancelar',
        compute='_compute_can_cancel',
    )
    random_value = fields.Float(string='Valor Aleatorio', default=0.0)

    # --- Campos relacionados (para mostrar en vistas sin joins manuales) ---

    raffle_state = fields.Selection(related='raffle_id.state', string='Estado Sorteo')
    product_name = fields.Char(related='raffle_id.product_id.name', string='Producto')
    ticket_price = fields.Float(related='raffle_id.ticket_price', string='Precio')
    currency_id = fields.Many2one(related='raffle_id.currency_id')

    _sql_constraints = [
        ('unique_raffle_number', 'UNIQUE(raffle_id, number)',
         'El numero de ticket debe ser unico por sorteo.'),
    ]

    # --- Campos computados ---

    @api.depends('purchase_date')
    def _compute_cancellation_deadline(self):
        """El cliente puede cancelar dentro de las 24 horas posteriores a la compra."""
        for rec in self:
            rec.cancellation_deadline = rec.purchase_date + timedelta(hours=24) if rec.purchase_date else False

    def _compute_can_cancel(self):
        """Determina si el ticket aun esta dentro de la ventana de cancelacion."""
        now = fields.Datetime.now()
        for rec in self:
            rec.can_cancel = (
                rec.state == 'sold'
                and rec.cancellation_deadline
                and now < rec.cancellation_deadline
            )

    # --- Acciones ---

    def action_reserve(self, partner_id=False, minutes=5):
        """Reserva temporal del ticket. Expira en N minutos."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != 'available':
                continue
            rec.write({
                'state': 'reserved',
                'reservation_partner_id': partner_id,
                'reservation_expiry': now + timedelta(minutes=minutes),
            })

    def action_release_expired(self):
        """Libera tickets cuya reserva expiro. Llamado por cron cada minuto."""
        expired = self.search([
            ('state', '=', 'reserved'),
            ('reservation_expiry', '<=', fields.Datetime.now()),
        ])
        expired._release_reservation()
        return True

    def _release_reservation(self):
        """Libera la reserva: vuelve a disponible y limpia datos.
        Tambien elimina la linea del carrito asociada (si no viene del unlink de SOL)."""
        if not self.env.context.get('skip_sol_unlink'):
            for rec in self:
                sol = self.env['sale.order.line'].sudo().search([
                    ('raffle_ticket_id', '=', rec.id),
                    ('order_id.state', '=', 'draft'),
                ], limit=1)
                if sol:
                    sol.with_context(skip_release=True).unlink()
        self.write({
            'state': 'available',
            'reservation_partner_id': False,
            'reservation_expiry': False,
        })

    def _get_raffle_responsible_user(self):
        """Obtiene el usuario responsable de sorteos configurado en ajustes.
        Si no hay configurado, usa el admin."""
        ICP = self.env['ir.config_parameter'].sudo()
        user_id = ICP.get_param('raffle_management.responsible_user_id', False)
        if user_id:
            user = self.env['res.users'].sudo().browse(int(user_id))
            if user.exists():
                return user
        return self.env.ref('base.user_admin')

    def action_cancel_ticket(self):
        """Cancelar ticket: lo libera, devuelve al pool de disponibles.
        Envia email ANTES de limpiar datos para que el template acceda a ellos."""
        for rec in self:
            if not rec.can_cancel:
                continue
            raffle = rec.raffle_id
            sol = rec.sale_order_line_id
            order = sol.order_id if sol else False
            partner_name = rec.partner_id.name or _('Cliente')
            ticket_price = raffle.ticket_price
            responsible = rec._get_raffle_responsible_user()
            company = raffle.company_id
            email_from = company.email_formatted or company.email

            # 1. Enviar email de cancelacion ANTES de limpiar (template accede a datos del ticket)
            ICP = self.env['ir.config_parameter'].sudo()
            if rec.partner_id.email and ICP.get_param('raffle_management.mail_cancellation', 'True') == 'True':
                template = self.env.ref(
                    'raffle_management.mail_template_raffle_cancellation', raise_if_not_found=False
                )
                if template:
                    template.sudo().send_mail(rec.id, email_values={'email_from': email_from})

            # 2. Restar semilla
            raffle.random_seed_sum -= rec.random_value

            # 3. Limpiar datos del ticket
            rec.write({
                'state': 'available',
                'partner_id': False,
                'sale_order_line_id': False,
                'purchase_date': False,
                'random_value': 0.0,
                'reservation_partner_id': False,
                'reservation_expiry': False,
            })

            # 4. Limpiar all_sold_date si el sorteo vuelve a tener tickets disponibles
            if raffle.all_sold_date:
                raffle.all_sold_date = False

            # 5. Nota interna + actividad + cancelar SO si corresponde
            if order and order.state == 'sale':
                order.sudo().message_post(
                    body=Markup(
                        '<b>Ticket cancelado por el cliente</b><br/>'
                        'Cliente: %s<br/>'
                        'Ticket: #%s (%s)<br/>'
                        'Sorteo: %s<br/>'
                        'Monto a reembolsar: %s<br/>'
                        'El ticket fue liberado y esta disponible nuevamente.'
                    ) % (partner_name, rec.number, rec.name, raffle.name, ticket_price),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                order.sudo().with_user(responsible).activity_schedule(
                    'mail.mail_activity_data_todo',
                    date_deadline=fields.Date.today(),
                    summary=_('Reembolso pendiente: Ticket #%s cancelado', rec.number),
                    note=_(
                        'El cliente %(partner)s cancelo el Ticket #%(number)s del sorteo %(raffle)s. '
                        'Monto a reembolsar: %(price)s. Gestionar reembolso manualmente.',
                        partner=partner_name,
                        number=rec.number,
                        raffle=raffle.name,
                        price=ticket_price,
                    ),
                    user_id=responsible.id,
                )
                remaining = order.order_line.filtered(
                    lambda l: l.raffle_ticket_id and l.raffle_ticket_id.state in ('sold', 'winner')
                )
                if not remaining:
                    order.sudo()._action_cancel()
