odoo.define('si_core.Dialog', function (require) {
   "use strict";

   let Dialog = require('web.Dialog');

   Dialog.include({
       /**
        * Intercept action handling to increase z-index of the last modal in order to blur the others.
        * @override
        */
       open: function (options) {
           let result = this._super.apply(this, arguments),
               modals_backdrop = $('.modal-backdrop.show'),
               modals = $('[role=dialog]'),
               modals_length = modals.length,
               backdrop_length = modals_backdrop.length;

           if (modals_length > 1) {
               let z_index = $(modals[modals_length - 2]).zIndex();
               $(modals_backdrop[backdrop_length - 1]).css('z-index', ++z_index);
               $(modals[modals_length - 1]).css('z-index', ++z_index);
           }

           return result;
       }
   })
});
