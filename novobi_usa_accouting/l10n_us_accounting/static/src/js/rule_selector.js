odoo.define('l10n_us_accounting.RuleSelector', function (require) {
    'use strict';

    var DomainSelector = require('web.DomainSelector');

    DomainSelector.include({

        _onAddFirstButtonClick: function () {
            if (this.model !== 'account.bank.statement.line') {
                this._addChild([['id', '=', 1]]);
            }
            else {
                this._addChild([['name', 'ilike', '']]);
            }
        }
    });
});