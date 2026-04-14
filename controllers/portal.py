from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

import base64


class RaffleCustomerPortal(CustomerPortal):
    """Extensión del portal para mostrar tickets de rifa del usuario.
    Agrega sección 'Mis Tickets de Rifa' en /my, lista de tickets comprados,
    cancelación de tickets (< 24h), subida de foto del ganador
    y campos editables de nickname/WhatsApp en /my/account."""

    def _prepare_home_portal_values(self, counters):
        """Agrega contador de tickets de rifa al home del portal."""
        values = super()._prepare_home_portal_values(counters)
        if 'raffle_ticket_count' in counters:
            partner = request.env.user.partner_id
            values['raffle_ticket_count'] = request.env['raffle.ticket'].search_count([
                ('partner_id', '=', partner.id),
                ('state', 'in', ('sold', 'winner')),
            ]) if request.env['raffle.ticket'].has_access('read') else 0
        return values

    def _get_optional_fields(self):
        """Agrega nickname y whatsapp_number como campos editables en /my/account."""
        return super()._get_optional_fields() + ['nickname', 'whatsapp_number']

    def on_account_update(self, values, partner):
        """Guarda nickname y whatsapp_number en el partner al actualizar la cuenta."""
        super().on_account_update(values, partner)
        raffle_fields = {k: values[k] for k in ('nickname', 'whatsapp_number') if k in values}
        if raffle_fields:
            partner.sudo().write(raffle_fields)

    @http.route(['/my/raffle/tickets', '/my/raffle/tickets/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_raffle_tickets(self, page=1, sortby=None, **kw):
        """Lista de tickets comprados por el usuario con paginación y ordenamiento."""
        partner = request.env.user.partner_id
        RaffleTicket = request.env['raffle.ticket'].sudo()

        domain = [
            ('partner_id', '=', partner.id),
            ('state', 'in', ('sold', 'winner')),
        ]

        searchbar_sortings = {
            'date': {'label': _('Fecha de Compra'), 'order': 'purchase_date desc'},
            'number': {'label': _('Número'), 'order': 'number asc'},
            'state': {'label': _('Estado'), 'order': 'state asc'},
        }
        if not sortby:
            sortby = 'date'
        sort_order = searchbar_sortings[sortby]['order']

        ticket_count = RaffleTicket.search_count(domain)
        pager = request.website.pager(
            url='/my/raffle/tickets',
            total=ticket_count,
            page=page,
            step=20,
            url_args={'sortby': sortby},
        )
        tickets = RaffleTicket.search(domain, order=sort_order, limit=20, offset=pager['offset'])

        values = self._prepare_portal_layout_values()
        values.update({
            'tickets': tickets,
            'page_name': 'raffle_tickets',
            'pager': pager,
            'default_url': '/my/raffle/tickets',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render('raffle_management.portal_my_raffle_tickets', values)

    @http.route('/my/raffle/ticket/cancel/<int:ticket_id>',
                type='http', auth='user', website=True, methods=['POST'])
    def portal_cancel_raffle_ticket(self, ticket_id, **kw):
        """Cancela un ticket del usuario si está dentro de las 24h.
        Libera el ticket y cancela la SO si no quedan tickets activos."""
        partner = request.env.user.partner_id
        ticket = request.env['raffle.ticket'].search([
            ('id', '=', ticket_id),
            ('partner_id', '=', partner.id),
            ('state', '=', 'sold'),
        ], limit=1)

        if not ticket or not ticket.can_cancel:
            return request.redirect('/my/raffle/tickets?error=cancel_failed')

        ticket.sudo().action_cancel_ticket()
        return request.redirect('/my/raffle/tickets?success=cancelled')

    @http.route('/my/raffle/ticket/upload_photo/<int:ticket_id>',
                type='http', auth='user', website=True, methods=['POST'])
    def portal_upload_winner_photo(self, ticket_id, **kw):
        """Permite al ganador subir su foto desde el portal.
        La foto se guarda en el sorteo y es obligatoria para la entrega."""
        partner = request.env.user.partner_id
        ticket = request.env['raffle.ticket'].search([
            ('id', '=', ticket_id),
            ('partner_id', '=', partner.id),
            ('state', '=', 'winner'),
        ], limit=1)
        if not ticket:
            return request.redirect('/my/raffle/tickets?error=upload_failed')

        photo = kw.get('winner_photo')
        if photo and hasattr(photo, 'read'):
            photo_data = base64.b64encode(photo.read())
            ticket.sudo().raffle_id.write({
                'winner_photo': photo_data,
                'winner_photo_filename': photo.filename,
            })
            return request.redirect('/my/raffle/tickets?success=photo_uploaded')
        return request.redirect('/my/raffle/tickets?error=no_photo')

    @http.route('/my/raffle/ticket/share_social/<int:ticket_id>',
                type='http', auth='user', website=True, methods=['POST'])
    def portal_share_social_url(self, ticket_id, **kw):
        """Permite al ganador compartir el link de su publicación en redes sociales.
        El link es obligatorio para que el admin pueda marcar como entregado."""
        partner = request.env.user.partner_id
        ticket = request.env['raffle.ticket'].search([
            ('id', '=', ticket_id),
            ('partner_id', '=', partner.id),
            ('state', '=', 'winner'),
        ], limit=1)
        if not ticket:
            return request.redirect('/my/raffle/tickets?error=upload_failed')

        social_url = kw.get('social_url', '').strip()
        if social_url:
            ticket.sudo().raffle_id.winner_social_url = social_url
            return request.redirect('/my/raffle/tickets?success=social_shared')
        return request.redirect('/my/raffle/tickets?error=no_url')
