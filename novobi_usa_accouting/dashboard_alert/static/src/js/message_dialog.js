odoo.define('dashboard_alert.MessageDialog', function (require) {
    "use strict";

    var Dialog = require('web.Dialog');


    var MessageDialog = Dialog.extend({
        init: function(parent, options) {
            options = (options || {});
            options.size = options.size || 'medium';
            var self = this;
            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: "OK", classes: "btn btn-primary", click: function() {
                        options.action_ok();
                        self.close();
                    }});
                if (options.confirm) {
                    options.buttons.push({text: "Cancel", classes: "btn o_form_button_cancel", click: function() {
                            if (options.action_cancel){
                                options.action_cancel();
                            }
                            self.close();
                        }});
                }
            }
            this._super(parent, options);
        }
    });

    return {
        MessageDialog: MessageDialog,
    };
});
