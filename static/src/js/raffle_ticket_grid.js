/** @odoo-module **/
/* Cuadrícula de tickets con reserva temporal (soft-lock 5 min).
   Distingue tickets propios (del carrito) vs ajenos.
   Click disponible → reservar. Click propio reservado → quitar. */

import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.RaffleTicketGrid = publicWidget.Widget.extend({
    selector: '.raffle-grid-container',
    events: {
        'click .raffle-ticket.raffle-available': '_onTicketClick',
        'click .raffle-ticket.raffle-reserved.raffle-mine': '_onMyReservedTicketClick',
    },

    start: function () {
        this.raffleId = this.el.dataset.raffleId;
        this._countdownIntervals = {};
        this._myTicketNumbers = [];
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

            // Al cargar, consultar qué tickets son míos y mostrar banner
            this._syncMyTickets();

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

    _syncMyTickets: async function () {
        /* Consulta al servidor qué tickets de este sorteo están en mi carrito. */
        if (!this.raffleId) return;
        try {
            const result = await rpc('/shop/raffle/ticket_status', {
                raffle_id: this.raffleId,
            });
            if (result.error) return;

            this._myTicketNumbers = [];
            const myIds = result.my_ticket_ids || [];

            result.tickets.forEach(t => {
                if (myIds.includes(t.id)) {
                    this._myTicketNumbers.push(t.number);
                }
            });

            this._applyMineClass(myIds);
            this._updateBanner();
        } catch (e) { /* ignore */ }
    },

    _applyMineClass: function (myTicketIds) {
        /* Marca visualmente los tickets propios con clase 'raffle-mine'. */
        this.el.querySelectorAll('.raffle-ticket.raffle-mine').forEach(el => {
            el.classList.remove('raffle-mine');
        });
        myTicketIds.forEach(id => {
            const el = this.el.querySelector(`.raffle-ticket[data-ticket-id="${id}"]`);
            if (el && el.dataset.ticketState === 'reserved') {
                el.classList.add('raffle-mine');
            }
        });
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

            const myIds = result.my_ticket_ids || [];
            this._myTicketNumbers = [];

            result.tickets.forEach(t => {
                const el = this.el.querySelector(
                    `.raffle-ticket[data-ticket-number="${t.number}"]`
                );
                if (!el) return;

                if (myIds.includes(t.id)) {
                    this._myTicketNumbers.push(t.number);
                }

                const currentState = el.dataset.ticketState;
                if (currentState !== t.state) {
                    el.classList.remove('raffle-available', 'raffle-reserved', 'raffle-sold', 'raffle-winner', 'raffle-cancelled', 'raffle-mine');
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
                }
            });

            this._applyMineClass(myIds);
            this._updateGridCounters();
            this._updateBanner();
        } catch (e) {
            console.error('Error refrescando cuadrícula:', e);
        }
    },

    // --- Click en ticket disponible: reservar ---
    _onTicketClick: function (ev) {
        if (this.readonly) return;
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

    // --- Click en MI ticket reservado: quitar ---
    _onMyReservedTicketClick: function (ev) {
        if (this.readonly) return;
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
                <p>¿Quitar del carrito?</p>
                <div class="d-flex gap-2 justify-content-center">
                    <button class="btn btn-sm btn-danger raffle-popup-confirm">
                        <i class="fa fa-times"></i> Quitar
                    </button>
                    <button class="btn btn-sm btn-secondary raffle-popup-cancel">
                        Mantener
                    </button>
                </div>
            </div>
        `;

        ticketEl.style.position = 'relative';
        ticketEl.appendChild(popup);

        popup.querySelector('.raffle-popup-confirm').addEventListener('click', async (e) => {
            e.stopPropagation();
            popup.remove();
            await this._removeTicketFromCart(ticketEl, ticketId, ticketNumber);
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

            ticketEl.classList.remove('raffle-available', 'raffle-loading');
            ticketEl.classList.add('raffle-reserved', 'raffle-mine');
            ticketEl.style.opacity = '1';
            ticketEl.dataset.ticketState = 'reserved';

            if (result.reservation_expiry) {
                this._startCountdown(ticketEl, result.reservation_expiry);
            }

            this._myTicketNumbers = result.my_ticket_numbers || [];
            this._updateCartBadge(result.cart_quantity);
            this._updateGridCounters();
            this._updateBanner();

        } catch (error) {
            console.error('Error al reservar ticket:', error);
            ticketEl.style.opacity = '1';
            ticketEl.classList.remove('raffle-loading');
            alert('Error al reservar el ticket. Intentá de nuevo.');
        }
    },

    _removeTicketFromCart: async function (ticketEl, ticketId, ticketNumber) {
        ticketEl.classList.add('raffle-loading');
        ticketEl.style.opacity = '0.5';

        try {
            const result = await rpc('/shop/raffle/remove_ticket', {
                ticket_id: ticketId,
            });

            if (result.error) {
                ticketEl.style.opacity = '1';
                ticketEl.classList.remove('raffle-loading');
                alert(result.error);
                return;
            }

            ticketEl.classList.remove('raffle-reserved', 'raffle-loading', 'raffle-mine');
            ticketEl.classList.add('raffle-available');
            ticketEl.style.opacity = '1';
            ticketEl.dataset.ticketState = 'available';

            const tn = ticketNumber.toString();
            if (this._countdownIntervals[tn]) {
                clearInterval(this._countdownIntervals[tn]);
                delete this._countdownIntervals[tn];
            }
            const countdownEl = ticketEl.querySelector('.raffle-countdown');
            if (countdownEl) countdownEl.remove();

            this._myTicketNumbers = result.my_ticket_numbers || [];
            this._updateCartBadge(result.cart_quantity);
            this._updateGridCounters();
            this._updateBanner();

        } catch (error) {
            console.error('Error al quitar ticket:', error);
            ticketEl.style.opacity = '1';
            ticketEl.classList.remove('raffle-loading');
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

    _updateBanner: function () {
        const section = this.el.closest('section');
        if (!section) return;

        const gridContainer = section.querySelector('.raffle-grid-container');
        if (!gridContainer) return;

        const existingBanner = section.querySelector('.raffle-checkout-banner');
        const numbers = this._myTicketNumbers;

        if (!numbers || numbers.length === 0) {
            if (existingBanner) existingBanner.remove();
            return;
        }

        const numbersText = numbers.map(n => `N° ${n}`).join(', ');
        const countText = numbers.length === 1
            ? `1 ticket seleccionado: ${numbersText}`
            : `${numbers.length} tickets seleccionados: ${numbersText}`;

        if (existingBanner) {
            const countSpan = existingBanner.querySelector('.raffle-banner-count');
            if (countSpan) countSpan.textContent = countText;
            return;
        }

        const banner = document.createElement('div');
        banner.className = 'raffle-checkout-banner sticky-top alert alert-success d-flex align-items-center justify-content-between py-2 px-3 mb-3';
        banner.style.zIndex = '100';
        banner.style.top = '60px';

        const payBtn = this.isPublic
            ? `<button class="btn btn-primary btn-sm ms-3 text-nowrap raffle-pay-btn">
                   <i class="fa fa-lock me-1"></i> Proceder al pago
               </button>`
            : `<a href="/shop/checkout?try_skip_step=true" class="btn btn-primary btn-sm ms-3 text-nowrap">
                   <i class="fa fa-lock me-1"></i> Proceder al pago
               </a>`;

        banner.innerHTML = `
            <span>
                <i class="fa fa-shopping-cart me-2"></i>
                <span class="raffle-banner-count fw-bold">${countText}</span>
                <span class="d-none d-md-inline"> — Tenés 5 minutos para completar la compra.</span>
            </span>
            ${payBtn}
        `;
        gridContainer.parentNode.insertBefore(banner, gridContainer);

        // Si es usuario público, el botón abre modal de login
        if (this.isPublic) {
            banner.querySelector('.raffle-pay-btn').addEventListener('click', () => {
                this._showLoginModal();
            });
        }
    },

    _showLoginModal: function () {
        // Remover modal previo si existe
        const prev = document.getElementById('raffleLoginModal');
        if (prev) prev.remove();

        const currentUrl = window.location.pathname;
        const modal = document.createElement('div');
        modal.id = 'raffleLoginModal';
        modal.className = 'raffle-login-modal';
        modal.innerHTML = `
            <div class="raffle-login-modal-backdrop"></div>
            <div class="raffle-login-modal-dialog">
                <div class="raffle-login-modal-content">
                    <div class="text-center mb-3">
                        <i class="fa fa-user-circle fa-3x text-primary"></i>
                    </div>
                    <h5 class="text-center mb-2">Para completar tu compra</h5>
                    <p class="text-center text-muted mb-4">
                        Necesitás iniciar sesión o crear una cuenta para proceder al pago.
                    </p>
                    <div class="d-flex flex-column gap-2">
                        <a href="/web/login?redirect=/shop/checkout?try_skip_step=true"
                           class="btn btn-primary w-100">
                            <i class="fa fa-sign-in me-2"></i> Iniciar sesión
                        </a>
                        <a href="/web/signup?redirect=/shop/checkout?try_skip_step=true"
                           class="btn btn-outline-primary w-100">
                            <i class="fa fa-user-plus me-2"></i> Crear cuenta
                        </a>
                    </div>
                    <button class="btn btn-link w-100 mt-2 text-muted raffle-login-modal-close">
                        Seguir eligiendo números
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Cerrar modal
        modal.querySelector('.raffle-login-modal-close').addEventListener('click', () => modal.remove());
        modal.querySelector('.raffle-login-modal-backdrop').addEventListener('click', () => modal.remove());
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
                    <i class="fa fa-check"></i> Ticket #${num} reservado
                </span>`;
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
