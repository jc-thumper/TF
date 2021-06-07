odoo.define('account_budget_advanced.usa_budget', function (require) {
'use strict';

var core = require('web.core');
var framework = require('web.framework');
var session = require('web.session');
var account_report = require('account_reports.account_report');
var field_utils = require('web.field_utils');

var usa_budget = account_report.extend({
    events: _.defaults({
        "click #btn_export": '_export_budget',
        "change input:radio[name=hide_zero]": '_change_zero_rows',
    }, account_report.prototype.events),

    render: function() {
        this._super();

        this.$("table").tableHeadFixer({'head': true, 'left': 1});
    },

    // ======= EVENTS ==================
    _change_zero_rows: function (e) {
        var self = this;
        var value;
        var display = $(e.target).val() === "yes" ? false : true;

        var rows = this.$("table tbody tr.o_js_account_report_inner_row");
        _.each(rows, function (row) {
            var tds = $(row).find("td:not(:first)");
            var skip = false;

            _.each(tds, function (td) {
                value = self._get_export_value($(td));
                if ($.isNumeric(value) &&  value != 0) {
                    skip = true;
                    return false;
                }
            });
            if (skip) {
                return false;
            }
            $(row).toggle(display);
        })
    },

    _export_budget: function (e) {
        var self = this;
        var rows = this.$("table tbody tr");

        var data = [];
        var row_dict;
        var row_data;
        var value;
        _.each(rows, function (row) {
            row_dict = {};
            row_data = [];

            row_dict['parent_id'] = $(row).data('parent-id') || 0;
            row_dict['total_id'] = $(row).data('total-id') || 0;
            row_dict['code'] = $(row).data('code') || '';
            row_dict['formulas'] = $(row).data('formulas') || '';
            row_dict['account_id'] = $(row).data('account-id') || '';

            var tds = $(row).find("td");
            _.each(tds, function (td) {
                value = self._get_export_value($(td));
                row_data.push(value);
            });
            row_dict['data'] = row_data;
            data.push(row_dict);
        });

        var options = {
            'data': data,
            'crossovered_budget_id': self.crossovered_budget_id,
            'groupby': self.groupby
        };
        var action_data = {
            financial_id: null,
            model: self.report_model,
            output_format: "xlsx",
            options: JSON.stringify(options),
        };

        // Export File
        framework.blockUI();
        var def = $.Deferred();
        session.get_file({
            url: '/account_reports',
            data: action_data,
            success: def.resolve.bind(def),
            error: function (error) {
                self.call('crash_manager', 'rpc_error', error);
                def.reject();
            },
            complete: framework.unblockUI,
        });
    },

    // ======= Helper Functions ==========
    // ===================================
    _formatNumbertoString: function(num) {
        num = num.toString().replace(/,/g, "");
        return field_utils.format.float(parseFloat(num));
    },

    _formatStringtoNumber: function(num) {
        num = num.toString().replace(/,/g, "");
        return num && parseFloat(num) || 0;
    },

    _get_export_value: function(td) {
        var self = this;
        var input_obj = td.find('input');  // input is for normal column
        var span_obj = td.find('span'); // Title in entry, or total column, or report
        if (span_obj.length > 0) {
            var separators = ['\\\n'];
            var regex = new RegExp(separators.join('|'), 'g');

            var value = span_obj.text().replace(regex, '').trim() || " ";
            var td_index = td.index();
            var return_value = td_index > 0 ? self._formatStringtoNumber(value) : value;
            return value.indexOf('%') > 0  ? value : return_value;
        }
        else if (input_obj.length > 0) {
            return input_obj.val() && self._formatStringtoNumber(input_obj.val()) || 0;
        }
    },

    _update_total_by_column: function (column_index) {
        var self = this;

        var total_tds = this.$("table tbody tr td[data-total-id]:nth-child(" + column_index + ")");
        _.each(total_tds, function (td) {
            var data_total_id = $(td).data('total-id');
            var sum = 0;

            var children = self.$("table tbody tr > td[data-parent-id=" + data_total_id + "]:nth-child(" + column_index + ")");
            _.each(children, function (child) {
                sum += self._get_export_value($(child));
            });
            $(td).find('span').html(self._formatNumbertoString(sum));
        });

        // FORMULA TDs
        var formula_tds = this.$("table tbody tr td[data-formulas]:nth-child(" + column_index + ")");

        var separators = ['\\\+', '-'];
        var regex = new RegExp(separators.join('|'), 'g');
        var spaceregex = new RegExp(' ', 'g');

        _.each(formula_tds, function (td) {
            var formula = $(td).data('formulas').replace(spaceregex, '');
            var codes = formula.split(regex);

            _.each(codes, function (code) {
                var sub_total = self.$("table tbody tr > td[data-code=" + code + "]:nth-child(" + column_index + ")");
                var sub_total_span = sub_total.find('span');
                window[code] = sub_total_span.html() && self._formatStringtoNumber(sub_total_span.html()) || 0 ;
            });

            var result = eval(formula);

            $(td).find('span').html(self._formatNumbertoString(result));
        });
    },
});

core.action_registry.add("usa_budget", usa_budget);
return usa_budget;
});
