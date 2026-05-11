/** @odoo-module **/
/* Countdown de reserva de tickets en la página del carrito (/shop/cart).
   Cada ticket maneja su expiración independientemente.
   Solo redirige cuando todas las líneas de rifa expiraron. */

import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.RaffleCartCountdown = publicWidget.Widget.extend({
    selector: '.js_cart_lines',

    start: function () {
        this._intervals = [];
        this._totalRaffleLines = 0;
        this._expiredCount = 0;
        this._startCountdowns();
        return this._super.apply(this, arguments);
    },

    destroy: function () {
        this._intervals.forEach(id => clearInterval(id));
        this._super.apply(this, arguments);
    },

    _startCountdowns: function () {
        const countdowns = this.el.querySelectorAll('.raffle-cart-countdown');
        if (!countdowns.length) return;

        this._totalRaffleLines = countdowns.length;

        countdowns.forEach(el => {
            const expiryStr = el.dataset.expiry;
            if (!expiryStr) return;

            const expiry = new Date(expiryStr);
            const timerSpan = el.querySelector('.raffle-cart-timer');
            const lineEl = el.closest('.o_cart_product');
            let expired = false;

            const update = () => {
                if (expired) return;

                const now = new Date();
                const diff = Math.max(0, Math.floor((expiry - now) / 1000));
                const min = Math.floor(diff / 60);
                const sec = diff % 60;
                timerSpan.textContent = `${min}:${sec.toString().padStart(2, '0')}`;

                if (diff <= 0) {
                    expired = true;
                    this._handleLineExpiration(el, lineEl);
                }
            };

            update();
            this._intervals.push(setInterval(update, 1000));
        });
    },

    _handleLineExpiration: async function (countdownEl, lineEl) {
        // Mostrar mensaje en esta línea
        countdownEl.innerHTML = '<i class="fa fa-exclamation-triangle"></i> Expirado';
        countdownEl.classList.remove('alert-warning');
        countdownEl.classList.add('alert-danger');

        // Eliminar esta línea del carrito vía AJAX
        const qtyInput = lineEl ? lineEl.querySelector('.js_quantity') : null;
        if (qtyInput) {
            const lineId = parseInt(qtyInput.dataset.lineId);
            const productId = parseInt(qtyInput.dataset.productId);
            if (lineId && productId) {
                try {
                    await rpc('/shop/cart/update_json', {
                        line_id: lineId,
                        product_id: productId,
                        set_qty: 0,
                    });
                } catch (e) { /* continuar aunque falle */ }
            }
        }

        // Ocultar la línea visualmente
        if (lineEl) {
            lineEl.style.opacity = '0.4';
            lineEl.style.pointerEvents = 'none';
        }

        // Contar expiradas
        this._expiredCount++;

        if (this._expiredCount >= this._totalRaffleLines) {
            // Todas las líneas de rifa expiraron → redirigir a la tienda
            this._intervals.forEach(id => clearInterval(id));
            setTimeout(() => {
                window.location.href = '/shop';
            }, 2000);
        }
    },
});

export default publicWidget.registry.RaffleCartCountdown;
