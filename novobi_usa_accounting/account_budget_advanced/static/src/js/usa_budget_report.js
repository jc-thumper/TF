odoo.define('account_budget_advanced.usa_budget_report', function (require) {
'use strict';

var core = require('web.core');
var usa_budget = require('account_budget_advanced.usa_budget');

var usa_budget_report = usa_budget.extend({
    init: function(parent, action) {
        this._super.apply(this, arguments);
    },

    render: function() {
        this._super();

        var self = this;
        this.column_number = this.report_options.column_number;
        this.crossovered_budget_id = this.report_options.crossovered_budget_id
        this.groupby = this.report_options.groupby;

        // run the 1st time, for loading existing data
        for (var i = 2; i <= self.column_number; i++) {
            self._update_total_by_column(i);
        }

        this._calculate_budget();
        // click event
        this._searchview_groupby();
    },

    _calculate_budget: function() {
        var self = this;
        var budget_cells = this.$("table tbody tr td[data-total-id].budget_cell");

        _.each(budget_cells, function (cell) {
            var column_index = $(cell).index() + 1;
            var row = $(cell).closest("tr");
            var positive = $(cell).data('positive');
            var budget_class = positive === 'True' && 'income_budget' || 'expense_budget';

            var actual_index = column_index-3;
            var budget_index = column_index-2;

            var actual_amount = self._formatStringtoNumber(row.find("td:nth-child(" + actual_index + ") span").html());
            var budget_amount = self._formatStringtoNumber(row.find("td:nth-child(" + budget_index + ") span").html());
            var percent = budget_amount && actual_amount/budget_amount*100 || 0;

            $(cell).find('span').html(self._formatNumbertoString(percent) + ' %');
            if (percent > 100){
                $(cell).addClass(budget_class);
            }
        });
    },

    // ======= Events ===================
    // ===================================
    _searchview_groupby: function(){
        var self = this;
        this.$searchview_buttons.find('.js_account_report_groupby_filter').click(function (event) {
            self.report_options.groupby.filter = $(this).data('filter');
            self.reload();
        });
    },
});

core.action_registry.add("usa_budget_report", usa_budget_report);
return usa_budget_report;
});
