odoo.define('l10n_us_accounting.ModelFieldSelectorUsa', function (require) {
    'use strict';

    var ModelFieldSelector = require('web.ModelFieldSelector');

    ModelFieldSelector.include({

        start: function () {
            if (this.model === 'account.bank.statement.line') {
                var fieldsList = ['name', 'amount_unsigned'];
                var pages = _.first(this.pages);
                this.pages = [_.map(fieldsList, function (item) {
                    return _.find(pages, function(page){
                        return page.name === item;
                    });
                })];
            }
            return this._super.apply(this, arguments);
        }
    });
});