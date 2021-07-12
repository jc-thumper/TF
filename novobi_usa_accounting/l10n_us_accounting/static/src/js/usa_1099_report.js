odoo.define('l10n_us_accounting.usa_1099_report', function (require) {
    'use strict';

    var core = require('web.core');
    var account_report = require('account_reports.account_report');
    var _t = core._t;


    var usa_1099_report = account_report.extend({
        events: _.defaults({
            "click #view_all_transaction": '_onViewAllTransactions',
        }, account_report.prototype.events),

        _onViewAllTransactions: function (ev) {
            var self = this;
            var options = $(ev.currentTarget).data('options');
            return self._rpc({
                model: 'vendor.1099.report',
                method: 'open_all_vendor_transactions',
                args: [options],
            })
                .then(function (result) {
                    return self.do_action(result);
                });
        },
    });

    core.action_registry.add("usa_1099_report", usa_1099_report);
    return usa_1099_report;
});
