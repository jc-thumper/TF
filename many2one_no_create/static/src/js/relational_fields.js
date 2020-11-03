odoo.define('many2one_no_create.relational_fields', function (require) {
    "use strict";

    var RelationalFields = require('web.relational_fields');


    return RelationalFields.FieldMany2One.include({
        init: function (parent, name, record, options) {
            this._super.apply(this, arguments);
            this.can_create = false;
        }
    });

});
