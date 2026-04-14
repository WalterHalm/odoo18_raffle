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
        Usado para refrescar la cuadrícula cuando expira una reserva."""
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
