odoo.define('account_budget_advanced.budget_controller', function (require) {
    'use strict';

    var core = require('web.core');
    var AbstractController = require('web.AbstractController');

    var BudgetController = AbstractController.include({

        _onOpenRecord: function (event) {
            event.stopPropagation();

            var self = this;
            var record = this.model.get(event.data.id, {raw: true});
            console.log(this.modelName);
            if (this.modelName == 'crossovered.budget') {
                return this._rpc({
                    model: 'crossovered.budget',
                    method: 'action_see_budget_report',
                    args: [[record.res_id]],
                }).then(function (action) {
                    self.trigger_up('do_action', {action: action});
                });
            }
            this._super(event);
        }
    });
});
