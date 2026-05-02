import random
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RaffleRaffle(models.Model):
    """Modelo principal de Sorteo.
    Gestiona el ciclo completo: creación → venta de tickets → sorteo → entrega.
    Separa el inventario del producto usando una ubicación virtual 'Sorteos'.
    """
    _name = 'raffle.raffle'
    _description = 'Sorteo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    # --- Campos principales ---

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo'),
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto a Sortear',
        required=True,
        domain=[('is_storable', '=', True), ('qty_available', '>', 0)],
        tracking=True,
    )
    ticket_product_id = fields.Many2one(
        'product.product',
        string='Producto Ticket (Tienda)',
        readonly=True,
        copy=False,
    )
    total_tickets = fields.Integer(
        string='Cantidad de Tickets',
        required=True,
    )
    product_value = fields.Float(
        string='Valor del Producto (Venta)',
        required=True,
        tracking=True,
    )
    suggested_ticket_price = fields.Float(
        string='Precio Sugerido por Ticket',
        compute='_compute_suggested_ticket_price',
        store=True,
    )
    ticket_price = fields.Float(
        string='Precio del Ticket',
        required=True,
        tracking=True,
    )

    # --- Estado del sorteo ---
    # Flujo: borrador → en_venta → completado → sorteo_pendiente → finalizado → entregado
    # En cualquier momento (excepto entregado) se puede cancelar

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('on_sale', 'En Venta'),
        ('completed', 'Completado'),
        ('draw_pending', 'Sorteo Pendiente'),
        ('finished', 'Finalizado'),
        ('delivered', 'Entregado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', required=True, tracking=True, copy=False)

    # --- Tickets ---

    ticket_ids = fields.One2many('raffle.ticket', 'raffle_id', string='Tickets')
    sold_tickets_count = fields.Integer(
        string='Tickets Vendidos',
        compute='_compute_ticket_counts',
        store=True,
    )
    available_tickets_count = fields.Integer(
        string='Tickets Disponibles',
        compute='_compute_ticket_counts',
        store=True,
    )
    progress = fields.Float(
        string='Progreso de Venta (%)',
        compute='_compute_ticket_counts',
        store=True,
    )

    # --- Sorteo y ganador ---

    auto_draw = fields.Boolean(
        string='Sorteo Automático',
        default=False,
        tracking=True,
        help='Si está activo, el sorteo se ejecuta automáticamente al vender el último ticket.',
    )
    draw_date = fields.Datetime(string='Fecha del Sorteo', tracking=True)
    winner_ticket_id = fields.Many2one('raffle.ticket', string='Ticket Ganador', readonly=True, copy=False)
    winner_partner_id = fields.Many2one('res.partner', string='Ganador', readonly=True, copy=False)
    winner_photo = fields.Binary(
        string='Foto del Ganador',
        copy=False,
        help='Foto opcional del ganador.',
    )
    winner_photo_filename = fields.Char(
        string='Nombre archivo foto',
        copy=False,
    )
    winner_social_url = fields.Char(
        string='Publicación en Redes',
        copy=False,
        help='Link a la publicación del ganador en redes sociales (Instagram, Facebook, TikTok, etc.).',
    )
    random_seed_sum = fields.Float(string='Semilla Acumulada', default=0.0, copy=False)
    all_sold_date = fields.Datetime(
        string='Fecha Todos Vendidos',
        copy=False,
        help='Fecha en que se vendió el último ticket. El sorteo se completa 34h después.',
    )

    # --- Stock (separación de inventario) ---

    stock_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación Sorteos',
        readonly=True,
        copy=False,
    )
    stock_move_reserve_id = fields.Many2one('stock.move', string='Movimiento Reserva', readonly=True, copy=False)
    stock_move_deliver_id = fields.Many2one('stock.move', string='Movimiento Entrega', readonly=True, copy=False)

    # --- Configuración ---

    category_id = fields.Many2one(
        'product.public.category',
        string='Categoría Tienda',
        default=lambda self: self.env.ref('raffle_management.raffle_public_category', raise_if_not_found=False),
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
    )
    product_image = fields.Binary(related='product_id.image_128', string='Imagen')

    # --- Campos computados ---

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Al seleccionar un producto, trae su precio de venta como valor por defecto."""
        if self.product_id:
            self.product_value = self.product_id.lst_price

    @api.depends('product_value', 'total_tickets')
    def _compute_suggested_ticket_price(self):
        """Calcula el precio sugerido dividiendo el valor del producto entre la cantidad de tickets.
        Según requerimiento del cliente: precio_sugerido = valor_producto / cantidad_tickets.
        El admin puede poner un precio mayor pero nunca menor."""
        for rec in self:
            rec.suggested_ticket_price = rec.product_value / rec.total_tickets if rec.total_tickets else 0.0

    @api.depends('ticket_ids.state')
    def _compute_ticket_counts(self):
        """Cuenta tickets vendidos y disponibles para mostrar progreso en el tablero.
        Requerimiento: mostrar total vendidos/disponibles con colores rojo/verde."""
        for rec in self:
            sold = len(rec.ticket_ids.filtered(lambda t: t.state in ('sold', 'winner')))
            available = len(rec.ticket_ids.filtered(lambda t: t.state == 'available'))
            rec.sold_tickets_count = sold
            rec.available_tickets_count = available
            rec.progress = (sold / rec.total_tickets * 100) if rec.total_tickets else 0.0

    # --- Validaciones ---

    @api.constrains('ticket_price', 'suggested_ticket_price')
    def _check_ticket_price(self):
        """Requerimiento: el precio del ticket solo puede ser igual o superior al sugerido."""
        for rec in self:
            if rec.ticket_price and rec.suggested_ticket_price and rec.ticket_price < rec.suggested_ticket_price:
                raise ValidationError(
                    _('El precio del ticket (%(price)s) no puede ser menor al sugerido (%(suggested)s).',
                      price=rec.ticket_price, suggested=rec.suggested_ticket_price)
                )

    @api.constrains('total_tickets')
    def _check_total_tickets(self):
        for rec in self:
            if rec.total_tickets <= 0:
                raise ValidationError(_('La cantidad de tickets debe ser mayor a 0.'))

    # --- CRUD ---

    @api.model_create_multi
    def create(self, vals_list):
        """Asigna secuencia automatica RIFA-0001, RIFA-0002, etc."""
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('raffle.raffle') or _('Nuevo')
        return super().create(vals_list)

    def unlink(self):
        """Solo permite eliminar sorteos en estado borrador o cancelado."""
        for rec in self:
            if rec.state not in ('draft', 'cancelled'):
                raise UserError(
                    _('No se puede eliminar el sorteo %s porque no esta en estado Borrador o Cancelado.', rec.name)
                )
        return super().unlink()

    # --- Acciones de flujo (botones del formulario) ---

    def action_confirm(self):
        """Confirmar sorteo: reserva stock, genera tickets y crea producto virtual en tienda.
        Flujo según requerimiento:
        1. Mueve producto a ubicación 'Sorteos' (separación de inventario)
        2. Genera N tickets numerados (ej: PROD-001, PROD-002...)
        3. Crea producto tipo servicio 'Ticket - [Producto]' publicado en categoría Rifas
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo se pueden confirmar sorteos en estado Borrador.'))
            rec._reserve_stock()
            rec._generate_tickets()
            rec._create_ticket_product()
            rec.state = 'on_sale'

    def action_open_draw_wizard(self):
        """Abre el wizard de ejecución del sorteo con resumen visual."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ejecutar Sorteo'),
            'res_model': 'raffle.draw.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_raffle_id': self.id},
        }

    def action_execute_draw(self):
        """Ejecutar el sorteo aleatorio usando la semilla acumulada."""
        for rec in self:
            sold_tickets = rec.ticket_ids.filtered(lambda t: t.state == 'sold')
            if not sold_tickets:
                raise UserError(_('No hay tickets vendidos para realizar el sorteo.'))
            seed = int(rec.random_seed_sum * 1000000) % (2**32)
            rng = random.Random(seed)
            winner = rng.choice(sold_tickets)
            winner.state = 'winner'
            rec.write({
                'winner_ticket_id': winner.id,
                'winner_partner_id': winner.partner_id.id,
                'state': 'finished',
            })
            rec._archive_ticket_product()
            rec._send_draw_emails()

    def _on_all_tickets_sold(self):
        """Se ejecuta cuando se vende el último ticket del sorteo.
        Registra la fecha pero NO cambia el estado. El sorteo sigue 'en venta'
        durante 34h para permitir cancelaciones. Un cron lo completará después."""
        self.ensure_one()
        self.all_sold_date = fields.Datetime.now()

    @api.model
    def action_complete_sold_raffles(self):
        """Cron: completa sorteos cuyo último ticket se vendió hace más de 34h.
        Si no hay tickets disponibles → pasa a 'completed' (y auto_draw si aplica).
        Si alguien canceló y hay tickets disponibles → limpia all_sold_date."""
        deadline = fields.Datetime.now() - timedelta(hours=24)
        raffles = self.search([
            ('state', '=', 'on_sale'),
            ('all_sold_date', '!=', False),
            ('all_sold_date', '<=', deadline),
        ])
        for raffle in raffles:
            available = raffle.ticket_ids.filtered(lambda t: t.state == 'available')
            if available:
                raffle.all_sold_date = False
            elif raffle.auto_draw:
                raffle.state = 'completed'
                raffle.action_execute_draw()
            else:
                raffle._compute_draw_date()
                raffle._archive_ticket_product()
                raffle.state = 'completed'

    def action_mark_delivered(self):
        """Marcar como entregado: descuenta stock físico moviendo de 'Sorteos' a cliente.
        Requiere link a publicación en redes sociales del ganador."""
        for rec in self:
            if rec.state != 'finished':
                raise UserError(_('Solo se puede entregar un sorteo Finalizado.'))
            if not rec.winner_social_url:
                raise UserError(_('El ganador debe compartir el link a su publicación en redes sociales antes de marcar como entregado.'))
            rec._deliver_stock()
            rec.state = 'delivered'

    def action_cancel(self):
        """Cancelar sorteo: libera stock reservado y desactiva producto ticket.
        Solo permitido en estados draft y on_sale. Sorteos con transacciones
        completadas (completed, finished, delivered) no se pueden cancelar."""
        for rec in self:
            if rec.state in ('completed', 'finished', 'delivered'):
                raise UserError(
                    _('No se puede cancelar el sorteo %s porque tiene transacciones. '
                      'Los sorteos completados o finalizados solo se ocultan de la tienda.', rec.name)
                )
            if rec.stock_move_reserve_id and rec.stock_move_reserve_id.state != 'done':
                rec.stock_move_reserve_id._action_cancel()
            elif rec.stock_move_reserve_id and rec.stock_move_reserve_id.state == 'done':
                rec._return_stock_to_origin()
            rec.ticket_ids.filtered(lambda t: t.state != 'cancelled').write({'state': 'cancelled'})
            if rec.ticket_product_id:
                rec._archive_ticket_product()
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        """Volver a borrador desde cancelado para poder reprogramar el sorteo."""
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Solo se puede volver a borrador desde Cancelado.'))
            rec.state = 'draft'

    def action_view_tickets(self):
        """Abrir vista de tickets filtrada por este sorteo (botón estadístico)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tickets - %s', self.name),
            'res_model': 'raffle.ticket',
            'view_mode': 'list,form',
            'domain': [('raffle_id', '=', self.id)],
            'context': {'default_raffle_id': self.id},
        }

    # --- Lógica de Stock (Separación de Inventario) ---

    def _get_raffle_location(self):
        """Obtiene la ubicación virtual 'Sorteos' creada por datos iniciales.
        Si no existe (caso edge), la crea dinámicamente.
        Requerimiento: producto separado del inventario disponible para venta normal."""
        location = self.env.ref('raffle_management.stock_location_raffles', raise_if_not_found=False)
        if not location:
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', self.company_id.id)], limit=1
            )
            location = self.env['stock.location'].create({
                'name': 'Sorteos',
                'usage': 'internal',
                'location_id': warehouse.view_location_id.id,
                'company_id': self.company_id.id,
            })
        return location

    def _reserve_stock(self):
        """Mueve 1 unidad del producto desde almacén principal a ubicación 'Sorteos'.
        Esto bloquea el producto para otros canales (POS, cotizaciones, etc.)
        porque ya no está en la ubicación de stock principal."""
        self.ensure_one()
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1
        )
        raffle_location = self._get_raffle_location()
        self.stock_location_id = raffle_location
        self.stock_move_reserve_id = self._do_stock_move(
            self.product_id, 1,
            warehouse.lot_stock_id, raffle_location,
            _('Reserva Sorteo: %s', self.name),
        )

    def _deliver_stock(self):
        """Mueve el producto de 'Sorteos' a ubicación cliente (entrega al ganador).
        Este es el momento donde se descuenta el stock físico real."""
        self.ensure_one()
        customer_location = self.env.ref('stock.stock_location_customers')
        self.stock_move_deliver_id = self._do_stock_move(
            self.product_id, 1,
            self.stock_location_id, customer_location,
            _('Entrega Sorteo: %s', self.name),
        )

    def _return_stock_to_origin(self):
        """Devuelve el producto de 'Sorteos' al almacén principal.
        Se usa al cancelar un sorteo cuyo stock ya fue movido."""
        self.ensure_one()
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1
        )
        self._do_stock_move(
            self.product_id, 1,
            self.stock_location_id, warehouse.lot_stock_id,
            _('Devolución Sorteo: %s', self.name),
        )

    def _do_stock_move(self, product, qty, src_location, dest_location, name):
        """Crea y valida un movimiento de stock inmediato entre dos ubicaciones.
        Patrón probado en Odoo 18/19: crear move → confirmar → limpiar demanda →
        crear move line con quantity y picked → marcar picked → _action_done."""
        move = self.env['stock.move'].create({
            'name': name,
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': product.uom_id.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'company_id': self.company_id.id,
            'origin': self.name,
        })
        move._action_confirm(merge=False)
        move.product_uom_qty = 0
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'product_id': product.id,
            'product_uom_id': product.uom_id.id,
            'quantity': qty,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'picked': True,
        })
        move.picked = True
        move._action_done()
        return move

    # --- Generación de Tickets ---

    def _generate_tickets(self):
        """Genera N tickets numerados secuencialmente.
        Requerimiento: usar código interno del producto como prefijo.
        Ejemplo: si el producto tiene código 'TV55', genera TV55-01, TV55-02, etc.
        Si no tiene código, usa 'RIFA' como prefijo."""
        self.ensure_one()
        prefix = self.product_id.default_code or 'RIFA'
        vals_list = [{
            'raffle_id': self.id,
            'number': i,
            'name': f'{prefix}-{str(i).zfill(len(str(self.total_tickets)))}',
        } for i in range(1, self.total_tickets + 1)]
        self.env['raffle.ticket'].create(vals_list)

    # --- Producto Virtual para Tienda ---

    def _archive_ticket_product(self):
        """Archiva el producto ticket para que desaparezca de la tienda."""
        self.ensure_one()
        if self.ticket_product_id:
            self.ticket_product_id.product_tmpl_id.active = False
            self.ticket_product_id.active = False

    def _create_ticket_product(self):
        """Crea un producto tipo servicio 'Ticket - [Producto]' para vender en la tienda.
        Requerimiento: al crear sorteo, generar automáticamente producto en categoría 'Rifas'.
        Se publica automáticamente en la tienda online con la imagen del producto original."""
        self.ensure_one()
        product = self.env['product.product'].create({
            'name': f'Ticket - {self.product_id.name}',
            'type': 'service',
            'list_price': self.ticket_price,
            'sale_ok': True,
            'purchase_ok': False,
            'is_raffle_ticket': True,
            'raffle_id': self.id,
            'categ_id': self.env.ref('product.product_category_all').id,
            'image_1920': self.product_id.image_1920,
        })
        # Publicar en tienda y asignar categoría pública (campos del template)
        tmpl = product.product_tmpl_id
        tmpl.website_published = True
        if self.category_id:
            tmpl.public_categ_ids = [(4, self.category_id.id)]
        self.ticket_product_id = product

    # --- Cálculo de Fecha de Sorteo ---

    def _compute_draw_date(self):
        """Calcula la fecha del sorteo según la regla del cliente:
        - Se toma como referencia el jueves
        - Si la venta se completa entre jueves y domingo, el sorteo es el
          fin de semana de la semana SIGUIENTE (sábado)
        - La fecha es editable manualmente por el admin"""
        self.ensure_one()
        now = fields.Datetime.now()
        weekday = now.weekday()  # 0=lunes, 3=jueves, 6=domingo
        if weekday >= 3:  # jueves a domingo → fin de semana siguiente
            days_until_next_saturday = (5 - weekday + 7) % 7
            if days_until_next_saturday == 0:
                days_until_next_saturday = 7
        else:  # lunes a miércoles → este fin de semana
            days_until_next_saturday = 5 - weekday
        draw_date = now + timedelta(days=days_until_next_saturday)
        self.draw_date = draw_date.replace(hour=20, minute=0, second=0)

    # --- Envío de Emails ---

    def _send_draw_emails(self):
        """Envía emails al ejecutar el sorteo: felicitación al ganador
        y resultado a todos los participantes. Respeta configuración de ajustes."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()

        company = self.company_id
        email_from = company.email_formatted or company.email

        # Email al ganador (template editable)
        if ICP.get_param('raffle_management.mail_winner', 'True') == 'True':
            template = self.env.ref(
                'raffle_management.mail_template_raffle_winner', raise_if_not_found=False
            )
            if template and self.winner_partner_id.email:
                template.send_mail(self.id,
                                   email_values={'email_from': email_from})

        # Email de resultados a participantes (template editable, queda en chatter del contacto)
        if ICP.get_param('raffle_management.mail_results', 'True') == 'True':
            template = self.env.ref(
                'raffle_management.mail_template_raffle_results', raise_if_not_found=False
            )
            if template:
                sold_tickets = self.ticket_ids.filtered(
                    lambda t: t.state == 'sold' and t.partner_id and t.partner_id.email
                )
                for ticket in sold_tickets:
                    template.send_mail(
                        ticket.id,
                        email_values={
                            'email_from': email_from,
                            'res_id': ticket.partner_id.id,
                            'model': 'res.partner',
                        },
                    )
