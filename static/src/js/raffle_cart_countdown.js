/** @odoo-module **/
/* Countdown de reserva de tickets en la página del carrito (/shop/cart).
   Cuando el timer llega a 0, recarga la página para reflejar la liberación. */

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.RaffleCartCountdown = publicWidget.Widget.extend({
    selector: '.js_cart_lines',

    start: function () {
        this._intervals = [];
        this._startCountdowns();
        return this._super.apply(this, arguments);
    },

    destroy: function () {
        this._intervals.forEach(id => clearInterval(id));
        this._super.apply(this, arguments);
    },

    _startCountdowns: function () {
        const countdowns = this.el.querySelectorAll('.raffle-cart-countdown');
        countdowns.forEach(el => {
            const expiryStr = el.dataset.expiry;
            if (!expiryStr) return;

            const expiry = new Date(expiryStr);
            const timerSpan = el.querySelector('.raffle-cart-timer');

            const update = () => {
                const now = new Date();
                const diff = Math.max(0, Math.floor((expiry - now) / 1000));
                const min = Math.floor(diff / 60);
                const sec = diff % 60;
                timerSpan.textContent = `${min}:${sec.toString().padStart(2, '0')}`;

                if (diff <= 0) {
                    // Reserva expiró, recargar para reflejar cambios
                    window.location.reload();
                }
            };

            update();
            this._intervals.push(setInterval(update, 1000));
        });
    },
});

export default publicWidget.registry.RaffleCartCountdown;
