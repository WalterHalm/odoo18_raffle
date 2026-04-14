from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RaffleDrawWizard(models.TransientModel):
    """Wizard para ejecutar el sorteo de forma visual.
    Muestra resumen del sorteo antes de ejecutar y confirma el ganador."""
    _name = 'raffle.draw.wizard'
    _description = 'Wizard de Ejecución de Sorteo'

    raffle_id = fields.Many2one('raffle.raffle', string='Sorteo', required=True)
    product_name = fields.Char(related='raffle_id.product_id.name', string='Producto')
    total_tickets = fields.Integer(related='raffle_id.total_tickets')
    sold_tickets_count = fields.Integer(related='raffle_id.sold_tickets_count')
    seed_sum = fields.Float(related='raffle_id.random_seed_sum', string='Semilla Acumulada')

    def action_execute_draw(self):
        """Ejecuta el sorteo delegando al método del modelo principal."""
        self.ensure_one()
        self.raffle_id.action_execute_draw()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'raffle.raffle',
            'res_id': self.raffle_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
