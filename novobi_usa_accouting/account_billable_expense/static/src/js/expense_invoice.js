odoo.define('account_billable_expense.BtnAssignExpense', function (require) {
    "use strict";

    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var data = require('web.data');
    var view_dialogs = require('web.view_dialogs');
    var ListView = require('web.ListView');
    var registry = require('web.field_registry');
    // var FieldChar = registry.get('char');
    var basic_fields = require('web.basic_fields');
    var FieldChar = basic_fields.FieldChar;
    var SelectCreateDialog = view_dialogs.SelectCreateDialog;
    var ListController = require('web.ListController');
    var ListRenderer = require('web.ListRenderer');
    var BasicView = require('web.BasicView');
    var _t = core._t;



    //Didn't change anything here, just need it
    var ViewDialog = Dialog.extend({
        custom_events: _.extend({}, Dialog.prototype.custom_events, {
            push_state: '_onPushState',
            env_updated: function (event) {
                event.stopPropagation();
            },
        }),
        /**
         * @constructor
         * @param {Widget} parent
         * @param {options} [options]
         * @param {string} [options.dialogClass=o_act_window]
         * @param {string} [options.res_model] the model of the record(s) to open
         * @param {any[]} [options.domain]
         * @param {Object} [options.context]
         */
        init: function (parent, options) {
            options = options || {};
            options.dialogClass = options.dialogClass || '' + ' o_act_window';

            this._super(parent, $.extend(true, {}, options));

            this.res_model = options.res_model || null;
            this.domain = options.domain || [];
            this.context = options.context || {};
            this.options = _.extend(this.options || {}, options || {});

            // FIXME: remove this once a dataset won't be necessary anymore to interact
            // with data_manager and instantiate views
            this.dataset = new data.DataSet(this, this.res_model, this.context);
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

        /**
         * We stop all push_state events from bubbling up.  It would be weird to
         * change the url because a dialog opened.
         *
         * @param {OdooEvent} event
         */
        _onPushState: function (event) {
            event.stopPropagation();
        },
    });

    //ListRenderer to render the lock on checkbox
    var USAListRenderer = ListRenderer.extend({
        _renderRow: function (record) {
            var self = this;
            this.defs = [];
            var $cells = _.map(this.columns, function (node, index) {
                return self._renderBodyCell(record, node, index, {mode: 'readonly'});
            });
            delete this.defs;

            var $tr = $('<tr/>', {class: 'o_data_row'})
                        .data('id', record.id)
                        .append($cells);
            if (this.hasSelectors) {
                $tr.prepend(self._renderSelector('td', record.data.invoice_line_id));
            }
            this._setDecorationClasses(record, $tr);
            return $tr;
        },

        _renderSelector: function (tag, state) {
            var $content = this.renderCheckbox(state);
            return $('<' + tag + ' width="1">')
                        .addClass('o_list_record_selector')
                        .append($content);
        },

        renderCheckbox: function (state) {
            var $container = $('<div class="o_checkbox"><input type="checkbox"/><span/></div>');
            if (state !== false && typeof state !== "undefined") {
                $container = $('<div class="o_checkbox"><span><i class="fa fa-lock"/></span><span/></div>');
            }
            return $container;
        },
    });

    //ListView to render the lock on checkbox
    var USAListView = ListView.extend({
        withSearchBar: false,
        // determines the search menus available and their orders
        searchMenuTypes: [],
        // determines if a control panel should be instantiated
        withControlPanel: false,
        // determines if a search panel could be instantiated
        withSearchPanel: false,
        config: _.extend({}, BasicView.prototype.config, {
            Renderer: USAListRenderer,
            Controller: ListController,
        }),
    });

    //Change custom_event function
    var SelectCreateListController = ListController.extend({
        // Override the ListView to handle the custom events 'open_record' (triggered when clicking on a
        // row of the list) such that it triggers up 'select_record' with its res_id.
        custom_events: _.extend({}, ListController.prototype.custom_events, {
            open_record: function (event) {
                event.stopPropagation();
                //var selectedRecord = this.model.get(event.data.id);
                //var bill_id = selectedRecord.data.bill_id.res_id;
                //
                //this.trigger_up('open_bill', {
                //    bill_id: bill_id,
                //    id: selectedRecord.res_id,
                //    display_name: selectedRecord.data.display_name
                //});
                //this.trigger_up('open_bill');
            }
        })
    });

    //Create a new Dialog for Assign Expense
    var AssignExpenseDialog = SelectCreateDialog.extend({
        custom_events: _.extend({}, ViewDialog.prototype.custom_events, {
            open_bill: function (event) {
                this.close();
            },

            // change state of button according to selected items
            selection_changed: function (event) {
                this.$footer.find(".o_add_items_btn").prop('disabled', !event.data.selection.length);
                this.$footer.find(".o_add_as_one_btn").prop('disabled', event.data.selection.length <= 1);
            },
        }),

        init: function (parent, params) {
            var self = this;
            this._super.apply(this, arguments);
        },

        //Change the view + logic here
        setup: function (fieldsViews) {
            var self = this;
            var fragment = document.createDocumentFragment();

            var domain = this.domain;
            if (this.initialIDs) {
                domain = domain.concat([['id', 'in', this.initialIDs]]);
            }

            var listView = new USAListView(fieldsViews.list, _.extend({
                context: this.context,
                domain: domain,
                modelName: this.res_model,
                hasSelectors: !self.options.disable_multiple_selection,
                readonly: true,
                withBreadcrumbs: false,
                withSearchPanel: false,
            }, self.options.list_view_options));
            listView.setController(SelectCreateListController);

            return listView.getController(self).then(function (controller) {
                self.viewController = controller;
                self.__buttons = [{
                    text: _t("Cancel"),
                    classes: "btn-secondary",
                    close: true,
                }];

                self.__buttons.unshift({
                    text: _t("Add as one item"),
                    classes: "btn-secondary o_add_as_one_btn",
                    disabled: true,
                    close: true,
                    click: function () {
                        var records = self.viewController.getSelectedRecords();

                        var values = _.map(records, function (record) {
                            return record.res_id
                        });
                        self.on_selected(values, 'one');
                    },
                });

                self.__buttons.unshift({
                    text: _t("Add items"),
                    classes: "btn-primary o_add_items_btn",
                    disabled: true,
                    close: true,
                    click: function () {
                        var records = self.viewController.getSelectedRecords();

                        var values = _.map(records, function (record) {
                            return record.res_id
                        });
                        self.on_selected(values, 'item');
                    },
                });
                return self.viewController.appendTo(fragment);
            }).then(function () {
                self.viewController.do_show();
                return fragment;
            });
        },
    });

    var BtnAssignExpense = FieldChar.extend({
        template: 'account_billable_expense.assign_expense_btn',

        _renderEdit: function () {
            var def = this._super.apply(this, arguments);
            this.$el.removeClass('o_input');  // remove this class in Edit mode
            return def;
        },

        _render: function () {
            this._super();
            var self = this;
            // bind button
            this.$el.unbind('click').bind('click', function () {
                self.onClickExpenseBtn();
            });
        },

        onClickExpenseBtn: function () {
            var self = this;
            var formController = this.__parentedParent.__parentedParent;

            formController.saveRecord(formController.handle, {
                stayInEdit: true,
            }).then(function () {
                self.invoice_id = formController.model.get(formController.handle, {}).res_id;

                // get ids and open popup
                self._rpc({
                    model: 'account.move',
                    method: 'get_customer_billable_expenses',
                    args: [[self.invoice_id]],
                }).then(function (expense_ids) {
                    new AssignExpenseDialog(self, {
                        res_model: 'billable.expenses',
                        title: 'Select billable expenses',
                        no_create: true,
                        disable_multiple_selection: false,
                        initial_ids: expense_ids,
                        on_selected: function (values, mode) {
                            self.addItems(values, mode);
                        }
                    }).open();
                });
            })
        },

        addItems: function(values, mode) {
            var self = this;

            this._rpc({
                model: 'account.move',
                method: 'from_expense_to_invoice',
                args: [[self.invoice_id], values, mode],
            }).then(function(result) {
                self.trigger_up('reload');
            });

        }
    });

    registry.add('assign_expense_btn', BtnAssignExpense);

});
