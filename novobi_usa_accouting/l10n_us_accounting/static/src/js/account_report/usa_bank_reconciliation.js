odoo.define('l10n_us_accounting.usa_bank_reconciliation', function (require) {
'use strict';

var core = require('web.core');
var account_report = require('account_reports.account_report');
var Dialog = require('web.Dialog');
var field_utils = require('web.field_utils');
var _t = core._t;


var usa_bank_reconciliation = account_report.extend({
    events: _.defaults({
        "change *[name='blocked']": '_onSelectItem',
        "click #select_all": '_onSelectAll',
        "click #deselect_all": '_onDeselectAll',
        'click .bank-reconcile': 'bank_reconcile',
        'click .edit-info': 'edit_info',
        'click .close-without-save': 'close_unsave',
    }, account_report.prototype.events),

    init: function(parent, action) {
        this._super.apply(this, arguments);

        this.cleared_deposits = 0;
        this.cleared_payments = 0;
        this.cleared_balance = 0;
        this.difference_amount = 0;
        this.no_payments = 0;
        this.no_deposits = 0;

        this.currency_id = this.report_options.currency_id;
    },

    render: function() {
        this._super();

        // these values are fixed
        this.beginning_balance = parseFloat(this.$('#beginning_balance').attr("data-value")) || 0;
        this.ending_balance = parseFloat(this.$('#ending_balance').attr("data-value")) || 0;

        this._updateAmount();

        /* if all lines are selected, the select all input should be checked too
        if (this.$el.find("tbody input:not(:checked)").length === 0) {
            this.$('#select_all').prop('checked', true);
        }*/

        this.$('#aml_table').tablesorter();
    },

    bank_reconcile: function(e) {
        let data_id = $(e.target).data("id");
        let self = this;

        // Get id of transactions, include payments and adjustments in batch payment
        let aml_ids = [];
        _.each(this.$el.find("tbody input[checkbox-model='account.move.line']"), function(e) {
            aml_ids.push(parseInt(e.attributes['checkbox-id'].value));
        });

        return this._rpc({
            model: 'account.bank.reconciliation.data',
            method: 'check_difference_amount',
            args: [[parseInt(data_id)], aml_ids,
                self.difference_amount, self.cleared_payments, self.cleared_deposits],
        }).then(function (action) {
            self.do_action(action, {clear_breadcrumbs: true})
        });
    },

    edit_info: function(e) {
        let data_id = $(e.target).data("id");
        let self = this;

        this._rpc({
            model: 'account.bank.reconciliation.data',
            method: 'get_popup_form_id',
            args: [[parseInt(data_id)]]
        }).then(function (viewId) {
            self.do_action({
                name: 'Begin Reconciliation',
                type:'ir.actions.act_window',
                view_type: 'form',
                view_mode: 'form',
                res_model: 'account.bank.reconciliation.data',
                views: [[viewId || false, 'form']],
                res_id: parseInt(data_id),
                target: 'new',
                context: {edit_info: true}
            }, {on_close: function(){ return self.reload();}
            });
        });
    },

    close_unsave: function (e) {
        var data_id = $(e.target).data("id");
        var self = this;

        new Dialog(this, {
            title: _t("We'll remove all of your changes"),
            $content: $('<div/>').html(
                _t("We'll reset all the transactions to their original state when you opened this reconciliation session. " +
                    "We'll also remove the statement info that you entered. Are you sure you want to close without saving?")
            ),
            buttons: [
                {text: _t('OK'), classes : "btn-primary", click: function() {
                    self._rpc({
                        model: 'account.bank.reconciliation.data',
                        method: 'close_without_saving',
                        args: [[data_id]]
                    }).then(function (action) {
                        self.do_action(action, {clear_breadcrumbs: true});
                    })
                }},
                {text: _t("Cancel"), click: function() {
                }, close: true}
            ]
        }).open();
    },

    /**
     * Click Select/Deselect All
     * Update value of all checkboxes in the column
     */
    _massUpdate: function (checked) {
        let self = this;

        // Get id of transactions
        let aml_ids = [];
        _.each(self.$el.find("td[data-model^='account.move.line']"), function(e) {
            aml_ids.push($(e).data('id'));
        });

        let msg = "Are you sure you want to <strong>select</strong> all transactions?"
        if (checked === false) {
            msg = "Are you sure you want to <strong>deselect</strong> all transactions?"
        }
        new Dialog(this, {
            title: _t("Confirmation"),
            $content: $('<div/>').html(_t(msg)),
            buttons: [
                {text: _t('OK'), classes : "btn-primary", click: function() {
                    self.$('tbody input').prop('checked', checked);
                    self._updateAmount();

                    // Update to model
                    self._updateTemporaryReconciled('account.move.line', aml_ids, checked);
                }, close:true},
                {text: _t("Cancel"), click: function() {
                }, close: true}
            ]
        }).open();
    },

    _onSelectAll: function (event) {
        this._massUpdate(true);
    },

    _onDeselectAll: function (event) {
        this._massUpdate(false);
    },

    /**
     * On change of Select line checkbox
     * If uncheck => uncheck the Select All checkbox
     */
    _onSelectItem: function(event) {
        let checked = $(event.currentTarget).prop('checked') || false;

        // update table so we can sort the checkbox column
        this.$('#aml_table').trigger("update");

        /*if (!checked) {
            this.$('thead input').prop('checked', false);
            this.$('#select_all').show();
            this.$('#deselect_all').hide();
        }*/

        this._updateAmount();

        // Update to model
        let target_id = $(event.target).parents('tr').find('td[data-id]').data('id');
        let target_model = $(event.target).parents('tr').find('td[data-model]').data('model');
        this._updateTemporaryReconciled(target_model, target_id, checked);
    },

    /**
     * Count the value of all checked boxes and update summary amount
     */
    _updateAmount: function() {
        let cleared_deposits = 0, cleared_payments = 0, no_payments = 0, no_deposits = 0;
        _.each(this.$('tbody input:checked'), function(e) {
            if (e.attributes['credit']) {
                no_payments += 1;
                cleared_payments += parseFloat(e.attributes['credit'].value)
            }
            else if (e.attributes['debit']) {
                no_deposits += 1;
                cleared_deposits += parseFloat(e.attributes['debit'].value)
            }
            else { // for deposits with 0 value
                no_deposits += 1;
            }
        });

        this.no_payments = no_payments;
        this.no_deposits = no_deposits;
        this.cleared_deposits = cleared_deposits;
        this.cleared_payments = cleared_payments;
        this.cleared_balance = this.beginning_balance - this.cleared_payments + this.cleared_deposits;
        this.difference_amount = this.ending_balance - this.cleared_balance;

        this.renderBalance();
    },

    /**
     * Call function to update temporary reconciled field
     */
    _updateTemporaryReconciled: function(model, ids, checked) {
        return this._rpc({
            model: model,
            method: 'update_temporary_reconciled',
            args: [[], ids, checked]
        })
    },

    _formatAmount: function(amount) {
        return field_utils.format.monetary(amount, {}, {
            currency_id: this.currency_id
        });
    },

    renderBalance: function() {
        this.$('#cleared_deposits').html(this._formatAmount(this.cleared_deposits));
        this.$('#cleared_payments').html(this._formatAmount(this.cleared_payments));
        this.$('#no_payments').text(this.no_payments);
        this.$('#no_deposits').text(this.no_deposits);
        this.$('#cleared_balance').html(this._formatAmount(this.cleared_balance));
        this.$('#difference_amount').html(this._formatAmount(this.difference_amount));
    },
    destroy: function () {
        //will be used to ask users' confirmation
        this._super.apply(this, arguments);
    }
});
core.action_registry.add("usa_bank_reconciliation", usa_bank_reconciliation);
return usa_bank_reconciliation;
});
