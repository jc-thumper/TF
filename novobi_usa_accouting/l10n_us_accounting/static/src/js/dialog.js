odoo.define('l10n_us_accounting.dialog', function (require) {
'use strict';

var core = require('web.core');
var Dialog = require('web.Dialog');
var field_utils = require('web.field_utils');

var USADialog = Dialog.include({
    init: function (parent, options) {
        this._super(parent, options);

        if (options !== undefined && 'action' in options) {
            this.hide_close_btn = options.action.hide_close_btn;
        }
    },

    willStart: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            if (self.hide_close_btn) {
                self.$modal.find('button[data-dismiss="modal"]').addClass('hidden');
            }
        });
    },
});
});
