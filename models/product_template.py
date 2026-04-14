from odoo import fields, models


class ProductTemplate(models.Model):
    """Herencia de product.template para agregar campos de sorteo.
    Cuando se confirma un sorteo, se crea un producto tipo servicio
    con is_raffle_ticket=True y raffle_id apuntando al sorteo.
    Estos campos se heredan automáticamente a product.product."""
    _inherit = 'product.template'

    is_raffle_ticket = fields.Boolean(
        string='Es Ticket de Rifa',
        default=False,
        help='Indica que este producto es un ticket de sorteo generado automáticamente.',
    )
    raffle_id = fields.Many2one(
        'raffle.raffle',
        string='Sorteo Asociado',
        help='Sorteo al que pertenece este producto ticket.',
    )
