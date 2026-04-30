import json

from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleRaffle(WebsiteSale):
    """Extensión del controller de tienda para inyectar datos de sorteo
    en la página de detalle del producto ticket."""

    def _prepare_product_values(self, product, category, search, **kwargs):
        """Agrega datos del sorteo y tickets al contexto de la página de producto."""
        values = super()._prepare_product_values(product, category, search, **kwargs)
        raffle = product.raffle_id
        if raffle and product.is_raffle_ticket:
            tickets = raffle.ticket_ids.sudo().sorted('number')
            values['raffle'] = raffle.sudo()
            values['raffle_tickets'] = tickets
            values['raffle_tickets_json'] = json.dumps([{
                'id': t.id,
                'number': t.number,
                'name': t.name,
                'state': t.state,
                'buyer': t.partner_id.display_nickname if t.partner_id else '',
                'reservation_expiry': (t.reservation_expiry.isoformat() + 'Z') if t.reservation_expiry else False,
            } for t in tickets])
        return values


class RaffleTicketController(http.Controller):
    """Controller separado para las rutas JSON de tickets de rifa.
    No hereda de WebsiteSale para evitar interferir con el checkout."""

    @http.route('/shop/raffle/add_ticket', type='json', auth='public', website=True)
    def raffle_add_ticket_to_cart(self, ticket_id, **kwargs):
        """Agrega un ticket específico al carrito de compras.
        El ticket se RESERVA por 5 minutos (soft-lock). Solo se marca como
        vendido al confirmar el pago. Si la reserva expira, vuelve a disponible."""
        ticket = request.env['raffle.ticket'].sudo().browse(int(ticket_id))
        if not ticket.exists() or ticket.state not in ('available',):
            return {'error': _('Este ticket ya no está disponible.')}

        raffle = ticket.raffle_id
        product = raffle.ticket_product_id
        if not product:
            return {'error': _('Producto de ticket no encontrado.')}

        sale_order = request.website.sale_get_order(force_create=True)
        existing_line = sale_order.order_line.filtered(
            lambda l: l.raffle_ticket_id.id == ticket.id
        )
        if existing_line:
            return {'error': _('Este ticket ya está en tu carrito.')}

        # Reservar ticket por 5 minutos
        partner_id = request.env.user.partner_id.id if not request.env.user._is_public() else False
        ticket.action_reserve(partner_id=partner_id, minutes=5)

        order_line = sale_order._cart_update(
            product_id=product.id,
            add_qty=1,
        )
        if order_line and order_line.get('line_id'):
            line = request.env['sale.order.line'].sudo().browse(order_line['line_id'])
            line.raffle_ticket_id = ticket.id

        return {
            'success': True,
            'ticket_number': ticket.number,
            'cart_quantity': sale_order.cart_quantity,
            'reservation_minutes': 5,
            'reservation_expiry': (ticket.reservation_expiry.isoformat() + 'Z') if ticket.reservation_expiry else False,
        }

    @http.route('/shop/raffle/ticket_status', type='json', auth='public', website=True)
    def raffle_ticket_status(self, raffle_id, **kwargs):
        """Devuelve el estado actual de todos los tickets de un sorteo.
        Usado para refrescar la cuadricula cuando expira una reserva."""
        raffle = request.env['raffle.raffle'].sudo().browse(int(raffle_id))
        if not raffle.exists():
            return {'error': 'Sorteo no encontrado'}
        tickets = raffle.ticket_ids.sorted('number')
        return {
            'tickets': [{
                'id': t.id,
                'number': t.number,
                'state': t.state,
                'buyer': t.partner_id.display_nickname if t.partner_id else '',
                'reservation_expiry': (t.reservation_expiry.isoformat() + 'Z') if t.reservation_expiry else False,
            } for t in tickets],
        }

    @http.route(['/ganadores', '/ganadores/page/<int:page>'], type='http', auth='public', website=True, sitemap=True)
    def raffle_winners(self, page=1, search='', **kw):
        """Pagina publica de ganadores con tarjetas narrativas, busqueda y paginacion."""
        domain = [
            ('state', 'in', ('finished', 'delivered')),
            ('winner_partner_id', '!=', False),
        ]
        if search:
            # Intentar buscar por numero de ticket si es digito
            ticket_domain = []
            if search.lstrip('#').isdigit():
                ticket_domain = [('winner_ticket_id.number', '=', int(search.lstrip('#')))]
            if ticket_domain:
                domain = ['&'] + domain + ['|', '|', '|',
                    ('product_id.name', 'ilike', search),
                    ('winner_partner_id.nickname', 'ilike', search),
                    ('winner_partner_id.name', 'ilike', search),
                ] + ticket_domain
            else:
                domain = ['&'] + domain + ['|', '|',
                    ('product_id.name', 'ilike', search),
                    ('winner_partner_id.nickname', 'ilike', search),
                    ('winner_partner_id.name', 'ilike', search),
                ]

        Raffle = request.env['raffle.raffle'].sudo()
        total = Raffle.search_count(domain)
        per_page = 10
        pager = request.website.pager(
            url='/ganadores',
            url_args={'search': search} if search else {},
            total=total,
            page=page,
            step=per_page,
        )
        raffles = Raffle.search(domain, order='create_date desc', limit=per_page, offset=pager['offset'])
        is_admin = request.env.user.has_group('raffle_management.group_raffle_manager')

        MESES = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
            5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
            9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre',
        }

        def format_date_es(dt):
            """Formatea datetime a '15 de abril de 2026'."""
            if not dt:
                return ''
            return '%d de %s de %d' % (dt.day, MESES[dt.month], dt.year)

        return request.render('raffle_management.raffle_winners_page', {
            'raffles': raffles,
            'pager': pager,
            'search': search,
            'is_admin': is_admin,
            'format_date_es': format_date_es,
        })

    @http.route('/ganadores/delete/<int:raffle_id>', type='http', auth='user', website=True, methods=['POST'])
    def raffle_winner_delete(self, raffle_id, **kw):
        """Elimina un sorteo de la lista de ganadores (solo admin)."""
        if not request.env.user.has_group('raffle_management.group_raffle_manager'):
            return request.redirect('/ganadores')
        raffle = request.env['raffle.raffle'].sudo().browse(raffle_id)
        if raffle.exists():
            raffle.winner_partner_id = False
        return request.redirect('/ganadores')

    @http.route('/sorteo/<int:raffle_id>', type='http', auth='public', website=True, sitemap=True)
    def raffle_public_view(self, raffle_id, **kw):
        """Pagina publica de un sorteo finalizado con cuadricula y ticket ganador dorado."""
        raffle = request.env['raffle.raffle'].sudo().browse(raffle_id)
        if not raffle.exists() or raffle.state not in ('finished', 'delivered'):
            return request.redirect('/ganadores')
        tickets = raffle.ticket_ids.sorted('number')
        tickets_json = json.dumps([{
            'id': t.id,
            'number': t.number,
            'name': t.name,
            'state': t.state,
            'buyer': t.partner_id.display_nickname if t.partner_id else '',
            'reservation_expiry': False,
        } for t in tickets])
        return request.render('raffle_management.raffle_public_view_page', {
            'raffle': raffle,
            'raffle_tickets': tickets,
            'raffle_tickets_json': tickets_json,
        })
