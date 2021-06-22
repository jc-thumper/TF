odoo.define('cash_flow_projection.cash_flow_projection_report', function (require) {
    "use strict";

    var core = require('web.core');
    var session = require('web.session');
    var AbstractAction = require('web.AbstractAction');
    var field_utils = require('web.field_utils');

    var QWeb = core.qweb;
    var _t = core._t;

    var cash_flow_projection = AbstractAction.extend({
        contentTemplate: 'CFP.template_content',
        hasControlPanel: true,
        events: {
            "click .o_cash_in_cell": "on_click_cash_in_cell",
            "click .o_period_name_cell": "on_click_period_cell",
            "change .o_cash_in_input_cell": "on_cash_in_change",
            "click .open_set_so_lead_time": "open_setting_so_lead_time",
            "click .open_set_recurring_cash_out": "open_setting_recurring_cash",
            "click .open_set_recurring_cash_in": "open_setting_recurring_cash",
        },
        init: function (parent, action) {
            this.action_manager = parent;
            this.action = action;
            this.domain = [];
            return this._super.apply(this, arguments);
        },
        willStart: function () {
            var self = this;
            return this._super.apply(this, arguments)
                .then(function () {
                    return self._rpc({
                        model: 'cash.flow.projection',
                        method: 'get_cash_flow_period_number',
                    })
                        .then(function (result) {
                            self.period_number = result['period_number'];
                            self.period = result['period_type'];
                            self.on_change_criteria();
                        })
                        .then(function () {
                            return self.reload_old_value()
                                .then(function () {
                                    self.renderButtons(self.options);
                                })
                        })
                });
        },
        do_show: function () {
            this._super.apply(this, arguments);
            this.updateControlPanel({
                title: _t('Cash Flow Projection'),
                cp_content: {
                    $buttons: this.$buttons,
                    $searchview_buttons: this.$searchview_buttons,
                },
            });
            this.action_manager.do_push_state({
                action: this.action.id,
            });
        },
        re_renderElement: function () {
            // this.$el.html(this.html);
            this.on_cash_in_change();
        },
        render: function () {
            var self = this;
            this._super.apply(this, arguments)
                .then(function () {
                    self.on_cash_in_change();
                });
        },
        get_html: function (e = null) {
            var self = this;
            return this._rpc({
                model: 'cash.flow.projection',
                method: 'get_html',
                args: [e],
                kwargs: {context: session.user_context},
            })
                .then(function (result) {
                     self.html_content = result.html;
                    $('.o_cfp_template_content').html(self.html_content);
                    self.report_context = result.report_context;
                    self.re_renderElement();
                });
        },
        on_cash_in_change: function (e) {
            var self = this;
            if (e) {
                try {
                    var change_value = field_utils.parse.float(e.currentTarget.value);
                    e.currentTarget.value = String(change_value.toFixed(2));
                    this.save_user_values(e);
                } catch (error) {
                    return this.do_warn(_t("Wrong value entered!"), error);
                }
            }

            var myTable = self.$('#projection_table')[0];
            var opening_balances = self.$('#opening_bank_balance')[0];
            var forward_balances = self.$('#opening_forward_balance')[0];
            // var closing_balances = self.$('#closing_bank_balance')[0];
            var total_cash_in = self.$('#total_cash_in')[0];
            var total_cash_out = self.$('#total_cash_out')[0];
            var cash_in = self.$('#cash_in')[0];
            var cash_out = self.$('#cash_out')[0];
            var cash_flow = self.$('#cash_flow')[0];
            var numberOfCol = myTable.rows[0].cells.length;
            var index_cash_in = total_cash_in.rowIndex;
            var index_cash_out = total_cash_out.rowIndex;
            var is_show_due_transaction = self.options['show_past_due_transaction'];
            for (var col = 1; col < numberOfCol; col++) {
                var total_cash_in_amount = 0.0;
                var total_cash_out_amount = 0.0;
                for (var row = cash_in.rowIndex + 1; row < index_cash_in; row++) {
                    try {
                        var firstChild = myTable.rows[row].cells[col].firstChild;
                        var value;
                        if (firstChild instanceof HTMLInputElement && firstChild.type == 'text') {
                            value = firstChild.value;
                            firstChild.value = self.numberWithCommas(value);
                        } else {
                            value = firstChild.nodeValue;
                            firstChild.nodeValue = self.numberWithCommas(value);
                        }
                        total_cash_in_amount += field_utils.parse.float(value);
                    } catch (error) {
                        return this.do_warn(_t("Wrong value entered!"), error);
                    }
                }
                for (var row = cash_out.rowIndex + 1; row < index_cash_out; row++) {
                    try {
                        var firstChild = myTable.rows[row].cells[col].firstChild;
                        var value;
                        if (firstChild instanceof HTMLInputElement && firstChild.type == 'text') {
                            value = firstChild.value;
                            firstChild.value = self.numberWithCommas(value);
                        } else {
                            value = firstChild.nodeValue;
                            firstChild.nodeValue = self.numberWithCommas(value);
                        }
                        total_cash_out_amount += field_utils.parse.float(value);
                    } catch (error) {
                        return this.do_warn(_t("Wrong value entered!"), error);
                    }
                }
                if ((col > 2 && is_show_due_transaction) || (col > 1 && !is_show_due_transaction)) {
                    forward_balances.cells[col].innerHTML = cash_flow.cells[col - 1].innerHTML;
                    opening_balances.cells[col].innerHTML = "<strong>0.00</strong>";
                } else {
                    forward_balances.cells[col].innerHTML = "<strong>0.00</strong>";
                    opening_balances.cells[col].innerHTML = `<strong>${self.numberWithCommas(field_utils.parse.float(opening_balances.cells[col].innerText).toFixed(2))}</strong>`;
                }
                var opening_balance_amount = field_utils.parse.float(opening_balances.cells[col].innerText);
                var opening_forward_amount = field_utils.parse.float(forward_balances.cells[col].innerText);
                total_cash_in.cells[col].innerHTML = `<strong>${String(self.numberWithCommas(total_cash_in_amount.toFixed(2)))}</strong>`;
                total_cash_out.cells[col].innerHTML = `<strong>${String(self.numberWithCommas(total_cash_out_amount.toFixed(2)))}</strong>`;
                var cash_flow_amount = opening_balance_amount + opening_forward_amount + total_cash_in_amount - total_cash_out_amount;
                cash_flow.cells[col].innerHTML = `<strong>${self.numberWithCommas(cash_flow_amount.toFixed(2))}</strong>`;
                // cash_flow.cells[col].style.backgroundColor = cash_flow_amount >= 0 ? "#4169E1" : "#FA8072";
                cash_flow.cells[col].style.color = cash_flow_amount >= 0 ? "#0000FF" : "#FF0000";
                // closing_balances.cells[col].innerHTML = `<strong>${String(self.numberWithCommas((field_utils.parse.float(opening_balances.cells[col].innerText) + total_cash_in_amount - total_cash_out_amount).toFixed(2)))}</strong>`;
            }
        },
        on_click_cash_in_cell: function (e) {
            var self = this;
            var code = $(e.currentTarget).data('trans-code');
            var index = $(e.currentTarget).index();
            return this._rpc({
                model: 'cash.flow.transaction.type',
                method: 'is_editable',
                args: [code],
            })
                .then(function (editable) {
                    if (editable && !(e.currentTarget.firstChild instanceof HTMLInputElement)) {
                        e.currentTarget.innerHTML = `<input type='text' class='o_cash_in_input_cell text-right input-number-cell' value='${field_utils.parse.float(e.currentTarget.firstChild.nodeValue).toFixed(2)}'/>`;
                    } else if (!editable) {
                        var period = self.period;
                        var period_name = $(e.currentTarget).data('period');
                        if (code == null) {
                            code = '';
                        }

                        var act = {
                            type: 'ir.actions.client',
                            name: _t('Cash Flow Detail Report'),
                            tag: 'account_report',
                            context: {
                                'model': 'account.cash.flow.report.detail',
                                'period_name': period_name,
                                'period_type': period,
                                'transaction_code': code,
                            },
                        };
                        return self.do_action(act);
                    }
                });

        },
        on_click_period_cell: function (e) {
            var index = $(e.currentTarget).index();
            var opening_balance = field_utils.parse.float(this.$('#opening_bank_balance')[0].cells[index].innerText);
            var forward_balance = field_utils.parse.float(this.$('#opening_forward_balance')[0].cells[index].innerText);
            var period = this.period;
            var period_name = $(e.currentTarget).data('period');

            var act = {
                type: 'ir.actions.client',
                name: _t('Cash Flow Detail Report'),
                tag: 'account_report',
                context: {
                    'model': 'account.cash.flow.report.detail',
                    'period_name': period_name,
                    'period_type': period,
                    'transaction_code': 'detail',
                    'opening_balance': opening_balance,
                    'forward_balance': forward_balance,
                },
            };
            return this.do_action(act);
        },
        numberWithCommas: function (x) {
            var stringValue = x.toString().replace(/,/g, "");
            var number = field_utils.parse.float(stringValue).toFixed(2);
            return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        },
        export_xlsx: function () {
            var self = this;
            var table_text = "<table border='2px'>";
            var table = self.$('#projection_table')[0];
            var numOfRow = table.rows.length;
            var opening_balance = self.$('#opening_bank_balance')[0].rowIndex;
            var forward_balance = self.$('#opening_forward_balance')[0].rowIndex;
            var total_cash_in = self.$('#total_cash_in')[0].rowIndex;
            var total_cash_out = self.$('#total_cash_out')[0].rowIndex;
            var cash_in = self.$('#cash_in')[0].rowIndex;
            var cash_out = self.$('#cash_out')[0].rowIndex;
            var cash_flow = self.$('#cash_flow')[0].rowIndex;
            for (var i = 0; i < numOfRow; i++) {
                var row = table.rows[i];
                var numOfCol = row.cells.length;
                var row_text = "";
                for (var j = 0; j < numOfCol; j++) {
                    var cell = row.cells[j];
                    var cell_text = "";
                    var bgStyle = "";
                    var colCharacter = self.get_excel_character_column(j + 1);
                    if (row.outerHTML.includes("class=\"table-active\"")) {
                        bgStyle = "bgcolor='#DDDDDD'";
                    } else if (row.outerHTML.includes("id=\"periods\"")) {
                        bgStyle = "bgcolor='#87AFC6'";
                    }
                    if (j == 0) {
                        var code = $(cell).data('trans-code');
                        if (code == 'sale_order' || code == 'purchase_order' || code == 'cash_in_other' || code == 'cash_out_other') {
                            cell_text = this.replaceInnerHtml(cell.outerHTML, cell.firstChild.textContent, bgStyle);
                        }
                    } else if (i == total_cash_in) {
                        var formula;
                        if (total_cash_in - cash_in > 1) {
                            formula = '=sum(' + colCharacter + String(cash_in + 2) + ':' + colCharacter + String(total_cash_in) + ')';
                        } else {
                            formula = '0.00';
                        }
                        cell_text = this.replaceInnerHtml(cell.outerHTML, formula, bgStyle);
                    } else if (i == total_cash_out) {
                        var formula;
                        if (total_cash_out - cash_out > 1) {
                            formula = '=sum(' + colCharacter + String(cash_out + 2) + ':' + colCharacter + String(total_cash_out) + ')';
                        } else {
                            formula = '0.00';
                        }
                        cell_text = this.replaceInnerHtml(cell.outerHTML, formula, bgStyle);
                    } else if (i == cash_flow) {
                        var formula = '=' + colCharacter + String(opening_balance + 1) + '+' + colCharacter + String(forward_balance + 1) + '+' + colCharacter + String(total_cash_in + 1) + '-' + colCharacter + String(total_cash_out + 1);
                        cell_text = this.replaceInnerHtml(cell.outerHTML, formula, bgStyle);
                    }
                    if (cell.firstChild instanceof HTMLInputElement) {
                        cell_text = this.replaceInnerHtml(cell.outerHTML, cell.firstChild.value, bgStyle);
                    } else if (cell_text == "") {
                        cell_text = this.replaceInnerHtml(cell.outerHTML, cell.innerHTML, bgStyle);
                    }
                    row_text = row_text + cell_text;
                }
                row_text = this.replaceInnerHtml(row.outerHTML, row_text, "");
                table_text = table_text + row_text;
            }
            table_text = table_text + "</table>";
            // Create download link element
            var downloadLink = document.createElement("a");
            downloadLink.href = 'data:application/vnd.ms-excel,' + encodeURIComponent(table_text);
            downloadLink.download = 'Cash_Flow_Projection.xls';
            downloadLink.click();
        },
        renderButtons: function (options) {
            var self = this;

            this.$buttons = $(QWeb.render("CFP.Buttons", {}));
            $(this.$buttons.filter('.o_btn_export')[0]).bind('click', function (event) {
                self.export_xlsx();
            });

            this.$searchview_buttons = $(QWeb.render("CFP.optionButton", options));
            this.$searchview_buttons.siblings('.o_cfp_period_filter');
            this.$searchview_buttons.find('.o_cfp_option_period').bind('click', function (event) {
                self.on_change_period(event);
            });
            this.$searchview_buttons.siblings('.o_cfp_transaction_filter');
            this.$searchview_buttons.find('.o_cfp_option_transaction_type').bind('click', function (event) {
                self.on_change_criteria(event);
            });
            this.$searchview_buttons.siblings('.o_cfp_set_period');
            this.$searchview_buttons.find('.o_btn_set_period').bind('click', function (event) {
                self.open_setting_number_of_period(event);
            });

            this.updateControlPanel({
                title: _t('Cash Flow Projection'),
                cp_content: {
                    $buttons: this.$buttons,
                    $searchview_buttons: this.$searchview_buttons,
                },
            });
            return this.$buttons;
        },
        replaceInnerHtml: function (outerHtml, replacedBy, bgStyle) {
            return outerHtml.replace(/>.*[\s\S]*</g, " " + bgStyle + ">" + replacedBy + "<");
        },
        on_change_period: function (e) {
            var self = this;
            this.period = $(e.target).data('value');
            this.options['period'] = this.period;
            this.options['num_period'] = self.period_number;
            return this.on_change_criteria()
                .then(function () {
                    self.renderButtons(self.options);
                    return self._rpc({
                        model: 'cash.flow.projection',
                        method: 'save_last_period_option',
                        args: [self.period],
                    })
                })
        },
        on_change_criteria: function (e = null) {
            var self = this;
            if (e) {
                var id = $(e.target).data('id');
                var code = $(e.target).data('value');
                var state = $(e.target).is(':checked');
                return this._rpc({
                    model: 'cash.flow.transaction.type',
                    method: 'set_active_transaction_type',
                    args: [id, code, state],
                })
                    .then(function () {
                        self.reload_old_value()
                            .then(function () {
                                self.get_html(self.options);
                            });
                    });
            }
            return this.reload_old_value()
                .then(function () {
                    self.get_html(self.options);
                });
        },
        reload_old_value: function () {
            var self = this;
            return this._rpc({
                model: 'cash.flow.transaction.type',
                method: 'get_all_record',
            })
                .then(function (result) {
                    self.options = result;
                    self.options['num_period'] = self.period_number;
                    self.options['period'] = self.period;
                    // self.renderButtons(self.options);
                });
        },
        save_user_values: function (e) {
            if (!e) {
                return
            }
            var self = this;
            var cell = $(e.currentTarget).parent();
            var code = $(cell).data('trans-code');
            var period = $(cell).data('period');
            var cash_type = $(cell).data('cash-type');
            var changeValue = field_utils.parse.float(e.currentTarget.value);
            var save_options = {
                'period': period,
                'period_type': self.period,
                'cash_type': cash_type,
                'code': code,
                'value': changeValue,
            };
            return this._rpc({
                model: 'cash.flow.projection',
                method: 'save_user_value',
                args: [save_options],
            });
        },
        open_setting_so_lead_time: function () {
            var self = this;
            return this._rpc({
                model: 'ir.model.data',
                method: 'get_object_reference',
                args: ['cash_flow_projection', 'cash_flow_setting_lead_time_form_view'],
            })
                .then(function (data) {
                    return self.do_action({
                        name: _t('Set up Due Date'),
                        type: 'ir.actions.act_window',
                        res_model: 'cash.flow.lead.time.setting',
                        views: [[data[1] || false, 'form']],
                        target: 'new',
                    });
                });
        },
        open_setting_number_of_period: function (e) {
            var self = this;
            return this._rpc({
                model: 'ir.model.data',
                method: 'get_object_reference',
                args: ['cash_flow_projection', 'cash_flow_setting_period_number_view'],
            })
                .then(function (data) {
                    return self.do_action({
                        name: _t('Set up Number of Periods'),
                        type: 'ir.actions.act_window',
                        res_model: 'cash.flow.period.setting',
                        views: [[data[1] || false, 'form']],
                        target: 'new',
                    })
                });
        },
        open_setting_recurring_cash: function (e) {
            var self = this;
            var cash_type = 'cash_in';
            var form_name = 'Update Recurring Cash In';
            if ($(e.target).hasClass('open_set_recurring_cash_out')) {
                cash_type = 'cash_out';
                form_name = 'Update Recurring Cash Out';
            }
            return this._rpc({
                model: 'cash.flow.user.configuration',
                method: 'get_recurring_value',
                args: [self.period, cash_type],
            })
                .then(function (result) {
                    return self._rpc({
                        model: 'ir.model.data',
                        method: 'get_object_reference',
                        args: ['cash_flow_projection', 'cash_flow_setting_recurring_cash_out_view'],
                    })
                        .then(function (data) {
                            return self.do_action({
                                name: _t(form_name),
                                type: 'ir.actions.act_window',
                                res_model: 'cash.flow.recurring.setting',
                                views: [[data[1] || false, 'form']],
                                target: 'new',
                                context: {
                                    'period_type': self.period,
                                    'cash_type': cash_type,
                                    'default_period_type': self.period,
                                    'default_amount': result,
                                },
                            });
                        });
                });
        },
        get_excel_character_column: function (number) {
            var str = "";
            while (number > 0) {
                let remainder = number % 26;
                if (remainder == 0) {
                    str = 'Z' + str;
                    number = Math.floor(number / 26) - 1;
                } else {
                    str = String.fromCharCode(remainder - 1 + 65) + str;
                    number = Math.floor(number / 26);
                }
            }
            return str;
        }
    });

    core.action_registry.add("cash_flow_projection", cash_flow_projection);
    return cash_flow_projection;
});
