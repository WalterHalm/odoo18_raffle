/** @odoo-module **/
/* Cuadrícula de tickets con reserva temporal (soft-lock 5 min).
   Click → reserva → countdown → confirmar pago o liberar. */

import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.RaffleTicketGrid = publicWidget.Widget.extend({
    selector: '.raffle-grid-container',
    events: {
        'click .raffle-ticket.raffle-available': '_onTicketClick',
    },

    start: function () {
        this.raffleId = this.el.dataset.raffleId;
        this._countdownIntervals = {};

        // Iniciar countdowns para tickets ya reservados
        this._initExistingReservations();

        // Buscador
        const section = this.el.closest('section');
        if (section) {
            const searchBtn = section.querySelector('.raffle-search-btn');
            const searchInput = section.querySelector('.raffle-search-input');
            if (searchBtn && searchInput) {
                searchBtn.addEventListener('click', () => this._onSearch(searchInput, section));
                searchInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') this._onSearch(searchInput, section);
                });
            }
        }

        // Refrescar cuadrícula cada 30 segundos
        this._refreshInterval = setInterval(() => this._refreshGrid(), 30000);

        return this._super.apply(this, arguments);
    },

    destroy: function () {
        // Limpiar todos los intervalos
        Object.values(this._countdownIntervals).forEach(id => clearInterval(id));
        if (this._refreshInterval) clearInterval(this._refreshInterval);
        this._super.apply(this, arguments);
    },

    _initExistingReservations: function () {
        /* Inicia countdowns para tickets que ya están reservados al cargar la página */
        try {
            const ticketsData = JSON.parse(this.el.dataset.tickets || '[]');
            ticketsData.forEach(t => {
                if (t.state === 'reserved' && t.reservation_expiry) {
                    const ticketEl = this.el.querySelector(
                        `.raffle-ticket[data-ticket-number="${t.number}"]`
                    );
                    if (ticketEl) {
                        this._startCountdown(ticketEl, t.reservation_expiry);
                    }
                }
            });
        } catch (e) { /* ignore parse errors */ }
    },

    _startCountdown: function (ticketEl, expiryIso) {
        /* Muestra countdown en el ticket reservado. Al expirar, refresca la cuadrícula. */
        const ticketNumber = ticketEl.dataset.ticketNumber;

        // Limpiar countdown previo si existe
        if (this._countdownIntervals[ticketNumber]) {
            clearInterval(this._countdownIntervals[ticketNumber]);
        }

        const expiry = new Date(expiryIso);
        const numberSpan = ticketEl.querySelector('.raffle-ticket-number');
        const originalText = numberSpan.textContent;

        // Crear elemento de countdown
        let countdownEl = ticketEl.querySelector('.raffle-countdown');
        if (!countdownEl) {
            countdownEl = document.createElement('span');
            countdownEl.className = 'raffle-countdown';
            ticketEl.appendChild(countdownEl);
        }

        const updateCountdown = () => {
            const now = new Date();
            const diff = Math.max(0, Math.floor((expiry - now) / 1000));
            const min = Math.floor(diff / 60);
            const sec = diff % 60;
            countdownEl.textContent = `${min}:${sec.toString().padStart(2, '0')}`;

            if (diff <= 0) {
                clearInterval(this._countdownIntervals[ticketNumber]);
                delete this._countdownIntervals[ticketNumber];
                countdownEl.remove();
                this._refreshGrid();
            }
        };

        updateCountdown();
        this._countdownIntervals[ticketNumber] = setInterval(updateCountdown, 1000);
    },

    _refreshGrid: async function () {
        /* Consulta el estado actual de los tickets y actualiza la cuadrícula */
        if (!this.raffleId) return;
        try {
            const result = await rpc('/shop/raffle/ticket_status', {
                raffle_id: this.raffleId,
            });
            if (result.error || !result.tickets) return;

            result.tickets.forEach(t => {
                const el = this.el.querySelector(
                    `.raffle-ticket[data-ticket-number="${t.number}"]`
                );
                if (!el) return;
                const currentState = el.dataset.ticketState;
                if (currentState === t.state) return;

                // Actualizar clase visual
                el.classList.remove('raffle-available', 'raffle-reserved', 'raffle-sold', 'raffle-winner', 'raffle-cancelled');
                el.classList.add(`raffle-${t.state}`);
                el.dataset.ticketState = t.state;
                el.dataset.buyer = t.buyer || '';

                // Limpiar countdown si ya no está reservado
                const ticketNumber = t.number.toString();
                const countdownEl = el.querySelector('.raffle-countdown');
                if (t.state !== 'reserved') {
                    if (this._countdownIntervals[ticketNumber]) {
                        clearInterval(this._countdownIntervals[ticketNumber]);
                        delete this._countdownIntervals[ticketNumber];
                    }
                    if (countdownEl) countdownEl.remove();
                } else if (t.reservation_expiry && !this._countdownIntervals[ticketNumber]) {
                    this._startCountdown(el, t.reservation_expiry);
                }
            });

            this._updateGridCounters();
        } catch (e) {
            console.error('Error refrescando cuadrícula:', e);
        }
    },

    _onSearch: function (input, section) {
        const resultDiv = section.querySelector('.raffle-search-result');
        const num = parseInt(input.value);
        const total = parseInt(this.el.dataset.total) || 0;

        if (!num || num < 1 || num > total) {
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `<span class="text-danger">
                <i class="fa fa-exclamation-circle"></i>
                Ingresá un número entre 1 y ${total}
            </span>`;
            return;
        }

        const ticketEl = this.el.querySelector(
            `.raffle-ticket[data-ticket-number="${num}"]`
        );
        if (!ticketEl) {
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `<span class="text-danger">
                <i class="fa fa-exclamation-circle"></i>
                Ticket #${num} no encontrado
            </span>`;
            return;
        }

        const state = ticketEl.dataset.ticketState;
        const ticketId = ticketEl.dataset.ticketId;

        ticketEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        ticketEl.classList.add('raffle-highlight');
        setTimeout(() => ticketEl.classList.remove('raffle-highlight'), 2000);

        if (state === 'available') {
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <span class="text-success">
                    <i class="fa fa-check-circle"></i>
                    Ticket #${num} está <strong>disponible</strong>
                </span>
                <button class="btn btn-sm btn-primary ms-2 raffle-search-add"
                        data-ticket-id="${ticketId}" data-ticket-number="${num}">
                    <i class="fa fa-cart-plus"></i> Agregar al carrito
                </button>
            `;
            resultDiv.querySelector('.raffle-search-add').addEventListener('click', async (e) => {
                const btn = e.currentTarget;
                await this._addTicketToCart(ticketEl, btn.dataset.ticketId, btn.dataset.ticketNumber);
                resultDiv.innerHTML = `<span class="text-success">
                    <i class="fa fa-check"></i> Ticket #${num} reservado (5 min para completar la compra)
                </span>`;
            });
        } else if (state === 'reserved') {
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `<span class="text-warning">
                <i class="fa fa-clock-o"></i>
                Ticket #${num} está <strong>reservado</strong> temporalmente
            </span>`;
        } else if (state === 'sold') {
            const buyer = ticketEl.dataset.buyer || 'Anónimo';
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `<span class="text-danger">
                <i class="fa fa-times-circle"></i>
                Ticket #${num} ya fue <strong>vendido</strong> a ${buyer}
            </span>`;
        } else if (state === 'winner') {
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `<span class="text-warning">
                <i class="fa fa-trophy"></i>
                Ticket #${num} es el <strong>ganador</strong>
            </span>`;
        }
    },

    _onTicketClick: function (ev) {
        const ticketEl = ev.currentTarget;
        if (ticketEl.classList.contains('raffle-loading')) return;

        const ticketNumber = ticketEl.dataset.ticketNumber;
        const ticketId = ticketEl.dataset.ticketId;

        document.querySelectorAll('.raffle-popup').forEach(el => el.remove());

        const popup = document.createElement('div');
        popup.className = 'raffle-popup';
        popup.innerHTML = `
            <div class="raffle-popup-content">
                <p><strong>Ticket #${ticketNumber}</strong></p>
                <p>Se reservará por <strong>5 minutos</strong></p>
                <div class="d-flex gap-2 justify-content-center">
                    <button class="btn btn-sm btn-primary raffle-popup-confirm">
                        <i class="fa fa-cart-plus"></i> Reservar
                    </button>
                    <button class="btn btn-sm btn-secondary raffle-popup-cancel">
                        Cancelar
                    </button>
                </div>
            </div>
        `;

        ticketEl.style.position = 'relative';
        ticketEl.appendChild(popup);

        popup.querySelector('.raffle-popup-confirm').addEventListener('click', async (e) => {
            e.stopPropagation();
            popup.remove();
            await this._addTicketToCart(ticketEl, ticketId, ticketNumber);
        });

        popup.querySelector('.raffle-popup-cancel').addEventListener('click', (e) => {
            e.stopPropagation();
            popup.remove();
        });

        setTimeout(() => {
            document.addEventListener('click', function closePopup(e) {
                if (!popup.contains(e.target)) {
                    popup.remove();
                    document.removeEventListener('click', closePopup);
                }
            });
        }, 100);
    },

    _addTicketToCart: async function (ticketEl, ticketId, ticketNumber) {
        ticketEl.classList.add('raffle-loading');
        ticketEl.style.opacity = '0.5';

        try {
            const result = await rpc('/shop/raffle/add_ticket', {
                ticket_id: ticketId,
            });

            if (result.error) {
                alert(result.error);
                ticketEl.style.opacity = '1';
                ticketEl.classList.remove('raffle-loading');
                return;
            }

            // Marcar como reservado (naranja) con countdown
            ticketEl.classList.remove('raffle-available', 'raffle-loading');
            ticketEl.classList.add('raffle-reserved');
            ticketEl.style.opacity = '1';
            ticketEl.dataset.ticketState = 'reserved';

            if (result.reservation_expiry) {
                this._startCountdown(ticketEl, result.reservation_expiry);
            }

            this._updateCartBadge(result.cart_quantity);
            this._updateGridCounters();

        } catch (error) {
            console.error('Error al reservar ticket:', error);
            ticketEl.style.opacity = '1';
            ticketEl.classList.remove('raffle-loading');
            alert('Error al reservar el ticket. Intentá de nuevo.');
        }
    },

    _updateCartBadge: function (cartQuantity) {
        const badges = document.querySelectorAll('.my_cart_quantity');
        badges.forEach(badge => {
            badge.classList.remove('d-none');
            badge.textContent = cartQuantity || '';
            badge.classList.add('o_mycart_zoom_animation');
            setTimeout(() => badge.classList.remove('o_mycart_zoom_animation'), 300);
        });
        document.querySelectorAll('li.o_wsale_my_cart').forEach(li => {
            li.classList.remove('d-none');
        });
        sessionStorage.setItem('website_sale_cart_quantity', cartQuantity);
    },

    _updateGridCounters: function () {
        const container = this.el;
        const available = container.querySelectorAll('.raffle-ticket.raffle-available').length;
        const sold = container.querySelectorAll('.raffle-ticket.raffle-sold').length
            + container.querySelectorAll('.raffle-ticket.raffle-winner').length;
        const total = container.querySelectorAll('.raffle-ticket').length;

        const section = container.closest('section');
        if (!section) return;

        const badges = section.querySelectorAll('.badge');
        badges.forEach(badge => {
            if (badge.textContent.includes('Disponibles')) {
                badge.innerHTML = `<i class="fa fa-check-circle"></i> Disponibles: ${available}`;
            } else if (badge.textContent.includes('Vendidos')) {
                badge.innerHTML = `<i class="fa fa-times-circle"></i> Vendidos: ${sold}`;
            }
        });

        const progressBar = section.querySelector('.progress-bar');
        if (progressBar && total > 0) {
            const pct = Math.round(sold / total * 100);
            progressBar.style.width = pct + '%';
            progressBar.textContent = pct + '% vendido';
        }
    },
});

export default publicWidget.registry.RaffleTicketGrid;
