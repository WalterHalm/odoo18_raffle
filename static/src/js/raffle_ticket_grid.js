/** @odoo-module **/
/* Cuadrícula de tickets - Flujo simplificado:
   Click ticket → reserva → redirect a pago (o login si no está logueado).
   Un ticket por compra. */

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
        this.readonly = this.el.dataset.readonly === '1';
        this.isPublic = this.el.dataset.isPublic === '1';

        if (!this.readonly) {
            this._initExistingReservations();

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

            // Si vuelve del login con un ticket pendiente, reservar y pagar
            this._refreshInterval = setInterval(() => this._refreshGrid(), 30000);
        }

        return this._super.apply(this, arguments);
    },

    destroy: function () {
        Object.values(this._countdownIntervals).forEach(id => clearInterval(id));
        if (this._refreshInterval) clearInterval(this._refreshInterval);
        this._super.apply(this, arguments);
    },

    _initExistingReservations: function () {
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
        } catch (e) { /* ignore */ }
    },

    _startCountdown: function (ticketEl, expiryIso) {
        const ticketNumber = ticketEl.dataset.ticketNumber;

        if (this._countdownIntervals[ticketNumber]) {
            clearInterval(this._countdownIntervals[ticketNumber]);
        }

        const expiry = new Date(expiryIso);

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

                el.classList.remove('raffle-available', 'raffle-reserved', 'raffle-sold', 'raffle-winner', 'raffle-cancelled');
                el.classList.add(`raffle-${t.state}`);
                el.dataset.ticketState = t.state;
                el.dataset.buyer = t.buyer || '';

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

    _onTicketClick: function (ev) {
        if (this.readonly) return;
        const ticketEl = ev.currentTarget;
        if (ticketEl.classList.contains('raffle-loading')) return;

        const ticketId = ticketEl.dataset.ticketId;
        const ticketNumber = ticketEl.dataset.ticketNumber;

        // Si no está logueado, redirigir a login con redirect a reserva directa
        if (this.isPublic) {
            window.location.href = '/web/login?redirect=' + encodeURIComponent('/shop/raffle/reserve_and_pay/' + ticketId);
            return;
        }

        // Si está logueado, reservar y redirigir al pago
        this._reserveAndPay(ticketEl, ticketId, ticketNumber);
    },

    _reserveAndPay: async function (ticketEl, ticketId, ticketNumber) {
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

            // Redirigir directo al pago
            window.location.href = '/shop/checkout?try_skip_step=true';

        } catch (error) {
            console.error('Error al reservar ticket:', error);
            ticketEl.style.opacity = '1';
            ticketEl.classList.remove('raffle-loading');
            alert('Error al reservar el ticket. Intentá de nuevo.');
        }
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
                    <i class="fa fa-cart-plus"></i> Comprar
                </button>
            `;
            resultDiv.querySelector('.raffle-search-add').addEventListener('click', (e) => {
                const btn = e.currentTarget;
                this._onTicketClick({ currentTarget: ticketEl });
            });
        } else if (state === 'reserved') {
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `<span class="text-warning">
                <i class="fa fa-clock-o"></i>
                Ticket #${num} está <strong>reservado</strong>
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
});

export default publicWidget.registry.RaffleTicketGrid;
