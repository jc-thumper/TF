odoo.define('l10n_us_accounting.RuleDomain', function (require) {
    'use strict';

    var BasicFields = require('web.basic_fields');
    var registry = require('web.field_registry');

    var RuleDomain = BasicFields.FieldDomain.extend({
        _replaceContent: function () {
            if (this._domainModel !== 'account.bank.statement.line') {
                this._super.apply(this, arguments);
            }
        }
    });

    registry.add('rule_domain', RuleDomain);
});