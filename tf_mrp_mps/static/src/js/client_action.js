odoo.define('tf_mrp_mps.ClientAction', function (require) {
'use strict';

let ClientAction = require('mrp_mps.ClientAction');

ClientAction.include({
    events: _.extend({}, ClientAction.prototype.events, {
            'click .o_mrp_mps_import_export': '_onClickImportExport',
        }),

    _onClickImportExport: function (ev){
        ev.preventDefault();
        let self = this
        this._rpc({
            model: 'mrp.production.schedule',
            method: 'open_table',
        }).then(function(action){
            self.do_action(action);
        })
    },

});

return ClientAction;

});
