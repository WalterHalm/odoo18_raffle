import random

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    """Herencia de sale.order.line para vincular la venta con un ticket de sorteo.
    Cuando se confirma una orden que contiene un producto ticket de rifa,
    se asigna el ticket al comprador y se acumula la semilla aleatoria."""
    _inherit = 'sale.order.line'

    raffle_ticket_id = fields.Many2one(
        'raffle.ticket',
        string='Ticket de Rifa',
        copy=False,
    )

    def unlink(self):
        """Al eliminar una línea del carrito que tiene ticket reservado,
        liberar la reserva para que vuelva a estar disponible."""
        if not self.env.context.get('skip_release'):
            for line in self:
                if line.raffle_ticket_id and line.raffle_ticket_id.state == 'reserved':
                    line.raffle_ticket_id.with_context(skip_sol_unlink=True)._release_reservation()
        return super().unlink()

    @api.depends('raffle_ticket_id')
    def _compute_name(self):
        """Extiende el compute del nombre para que se recompute
        cuando se asigna un ticket de rifa."""
        super()._compute_name()

    def _get_sale_order_line_multiline_description_sale(self):
        """Agrega el número de ticket a la descripción de la línea de venta.
        Ejemplo: 'Ticket - TV Samsung (#42)'"""
        description = super()._get_sale_order_line_multiline_description_sale()
        if self.raffle_ticket_id:
            description += '\n🎟️ Ticket #%s' % self.raffle_ticket_id.number
        return description

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Al confirmar la orden de venta, si la línea tiene un ticket de rifa
        asignado, se marca como vendido y se acumula la semilla."""
        res = super()._action_launch_stock_rule(previous_product_uom_qty)
        for line in self.filtered(lambda l: l.raffle_ticket_id and l.raffle_ticket_id.state in ('available', 'reserved')):
            line._sell_raffle_ticket()
        return res

    def _sell_raffle_ticket(self):
        """Registra la venta del ticket: asigna comprador, genera semilla aleatoria,
        y verifica si el sorteo se completó (último ticket vendido).
        Requerimiento: cada venta genera un valor aleatorio acumulativo."""
        self.ensure_one()
        ticket = self.raffle_ticket_id
        raffle = ticket.raffle_id
        random_value = random.uniform(0, 1000000)

        ticket.write({
            'state': 'sold',
            'partner_id': self.order_id.partner_id.id,
            'sale_order_line_id': self.id,
            'purchase_date': fields.Datetime.now(),
            'random_value': random_value,
            'reservation_partner_id': False,
            'reservation_expiry': False,
        })
        raffle.random_seed_sum += random_value

        # Verificar si se vendieron todos los tickets → completar sorteo
        if not raffle.ticket_ids.filtered(lambda t: t.state == 'available'):
            raffle._on_all_tickets_sold()


class SaleOrder(models.Model):
    """Herencia de sale.order para que cada ticket de rifa
    sea una línea separada en el carrito (no agrupa cantidades)."""
    _inherit = 'sale.order'

    def _cart_find_product_line(self, product_id, line_id=None, **kwargs):
        """Para productos de rifa, no agrupar al agregar (line_id=None).
        Cuando se edita/elimina (line_id dado), dejar el flujo nativo."""
        lines = super()._cart_find_product_line(product_id, line_id, **kwargs)
        if lines and not line_id:
            product = self.env['product.product'].browse(product_id)
            if product.is_raffle_ticket:
                return self.env['sale.order.line']
        return lines
