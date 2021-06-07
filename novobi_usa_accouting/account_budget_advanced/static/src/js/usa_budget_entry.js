odoo.define('account_budget_advanced.usa_budget_entry', function (require) {
'use strict';

var core = require('web.core');
var Dialog = require('web.Dialog');
var framework = require('web.framework');
var session = require('web.session');
var usa_budget = require('account_budget_advanced.usa_budget');

var _t = core._t;


var usa_budget_entry = usa_budget.extend({
    events: _.extend({}, usa_budget.prototype.events || {}, {
        "click #btn_save": '_save_budget',
        "click #btn_close": '_close_budget',
        "click #btn_delete": '_delete_budget',
        "click #btn_import": '_import_budget',
    }),

    render: function() {
        this._super();

        this.crossovered_budget_id = this.report_options.crossovered_budget_id;
        this.budget_wizard_id = this.report_options.budget_wizard_id;
        this.column_number = this.report_options.column_number;
        this.save_budget = true;  // true when click on save, false when change an input

        this._bind_table_row();

        if (this.report_options.save_budget_import) {
            this._save_budget();
        }
    },

    // ======= Buttons ==================
    // ===================================
    _save_budget: function (e) {
        var self = this;

        var budget_lines = {};
        _.each(this.$("tbody td.value_column input"), function(input) {
            var input_obj = $(input);
            var account_id = input_obj.closest('td').data('id');
            var array = budget_lines[account_id] || [];

            array.push(self._formatStringtoNumber(input_obj.val()));
            budget_lines[account_id] = array;
        });

        return self._rpc({
            model: 'crossovered.budget',
            method: 'update_budget_lines',
            args: [[self.crossovered_budget_id], budget_lines]
        }).then(function (e) {
            self.save_budget = true;

            $.notify({
                // options
                message: 'This budget has been saved successfully.'
            },{
                // settings
                type: 'success',
                offset: {
                    y: 50,
                },
                placement: {
                    from: "top",
                    align: "left"
                },
                delay: 200,
            });
        });
    },

    _close_budget: function (e) {
        var self = this;

        if (!this.save_budget) {
            new Dialog(this, {
                title: _t("Warning"),
                $content: $('<div/>').html(
                    _t("The budget has been modified, your changes will be discarded. Do you want to proceed?")
                ),
                buttons: [
                    {text: _t('OK'), classes : "btn-primary", click: function() {
                        self._rpc({
                            model: 'account.budget.wizard',
                            method: 'close_budget',
                            args: [[]]
                        }).then(function (action) {
                            self.do_action(action, {clear_breadcrumbs: true});
                        })
                    }},
                    {text: _t("Cancel"), click: function() {}, close: true}
                ]
            }).open();
        }
        else {
            self._rpc({
                model: 'account.budget.wizard',
                method: 'close_budget',
                args: [[]]
            }).then(function (action) {
                self.do_action(action, {clear_breadcrumbs: true});
            })
        }
    },

    _delete_budget: function (e) {
        var self = this;

        new Dialog(this, {
            title: _t("Confirmation"),
            $content: $('<div/>').html(
                _t("Are you sure you want to delete this budget?")
            ),
            buttons: [
                {text: _t('OK'), classes : "btn-primary", click: function() {
                    self._rpc({
                        model: 'account.budget.wizard',
                        method: 'delete_budget',
                        args: [[self.budget_wizard_id]]
                    }).then(function (action) {
                        self.do_action(action, {clear_breadcrumbs: true});
                    })
                }},
                {text: _t("Cancel"), click: function() {}, close: true}
            ]
        }).open();
    },

    _import_budget: function (e) {
        var self = this;

        return this._rpc({
            model: 'account.budget.wizard',
            method: 'import_budget_wizard',
            args: [[self.budget_wizard_id]],
        }).then(function (action) {
            self.do_action(action, {clear_breadcrumbs: true})
        });
    },

    // ======= Events ===================
    // ===================================
    _bind_table_row: function(){
        var self = this;
        var rows = this.$("table tbody tr");

        // run the 1st time, for loading existing data
        for (var i = 2; i <= self.column_number; i++) {
            self._update_total_by_column(i);
        }

        _.each(rows, function (row) {
            // run the 1st time, for loading existing data
            self._update_total_by_row($(row));

            // find the td with class value_column, add event listener
            $(row).find('.value_column').on('change', function () {
                self.save_budget = false;

                var column_index = $(this).index() + 1;  // because :nth-child is 1-based
                self._update_total_by_column(column_index);
                self._update_total_by_row($(row));
                self._update_total_by_column(self.column_number+1);  // the total column
            });
        });

        // run the 1st time, for the total column. Need to run after _update_total_by_row
        self._update_total_by_column(self.column_number+1);

        // formatting number
        this.$('.value_column input').on('change', function() {
            var $this = $(this);
            $this.val(self._formatNumbertoString($this.val()));
        });
    },

    _update_total_by_row: function (row) {
        var self = this;

        // Row Total
        var inputs = row.find(".value_column input");
        var sum = 0;
        inputs.each(function (j) {
            var input_obj = $(this);
            sum += input_obj.val() && self._formatStringtoNumber(input_obj.val()) || 0 ;
        });

        row.find('.total_column span').html(self._formatNumbertoString(sum));
    },
});

core.action_registry.add("usa_budget_entry", usa_budget_entry);
return usa_budget_entry;
});
