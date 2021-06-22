odoo.define('usa.account_report', function (require) {
    'use strict';

    var accountReportsWidget = require('account_reports.account_report');
    accountReportsWidget.include({
        renderButtons: function () {
            var self = this;
            var res = this._super();

            if (this.$buttons.length === 1) {
                $(this.$buttons).click(function () {
                    return self._rpc({
                        model: self.report_model,
                        method: $(self.$buttons).attr('action'),
                        args: [self.financial_id, self.report_options],
                        context: self.odoo_context,
                    }).then(function (result) {
                        return self.do_action(result);
                    });
                });
                return this.$buttons;
            }
            return res;
        },
    });
});