odoo.define('account_dashboard.kpi_header', function (require) {
    "use strict";

    /**
     * This file defines the US Accounting Dashboard view (alongside its renderer, model
     * and controller), extending the Kanban view.
     * The US Accounting Dashboard view is registered to the view registry.
     * A large part of this code should be extracted in an AbstractDashboard
     * widget in web, to avoid code duplication (see SalesTeamDashboard).
     */

    var core = require('web.core');
    var KanbanController = require('web.KanbanController');
    var KanbanModel = require('web.KanbanModel');
    var KanbanRenderer = require('web.KanbanRenderer');
    var KanbanView = require('web.KanbanView');
    var view_registry = require('web.view_registry');

    var QWeb = core.qweb;

    var _t = core._t;
    var _lt = core._lt;

    var HeaderKPIsRenderer = KanbanRenderer.extend({
        events:{
            'click #setting_header_btn': 'click_setting_header_btn',
            'click .close_setting_header_btn': 'click_setting_header_btn',
            'click .select_all_kpis_header_btn': 'click_select_all_kpis_btn',
            'change input.select_kpi': 'change_kpi_selections',
            'change .slide': 'change_order_kpi'
        },
        //--------------------------------------------------------------------------
        // EVENTS
        //--------------------------------------------------------------------------
        change_order_kpi: function () {
            console.log("change the order of list KPIs")
        },

        click_select_all_kpis_btn: function () {
            var self = this;
            var selections = this.$('input.select_kpi');
            var all_kpis = this.$('input.select_all_kpis');
            var select_all = all_kpis[0];
            var list_return = [];
            for (var idx = 0; idx < selections.length; idx++) {
                var selection = selections[idx];
                var name_kpi = $(selection).val();
                list_return.push({
                    'name_kpi': name_kpi,
                    'selected': select_all.checked
                })
            }

            this._rpc({
                model: 'personalized.kpi.info',
                method: 'update_kpi_selected',
                args: [list_return]

            }).then(function(data) {
                self._render_kpis(data.kpi_data);
                self._render_kpi_manage(data.kpi_info);
                self._set_action_move();
            });
        },

        change_kpi_selections: function () {
            var self = this;
            var selections = this.$('input.select_kpi');
            var list_return = [];
            for (var idx = 0; idx < selections.length; idx++) {
                var selection = selections[idx];
                var name_kpi = $(selection).val();
                var selected = selection.checked;
                list_return.push({
                    'name_kpi': name_kpi,
                    'selected': selected
                })
            }

            this._rpc({
                model: 'personalized.kpi.info',
                method: 'update_kpi_selected',
                args: [list_return]

            }).then(function(data) {
                self._render_kpis(data.kpi_data);
                self._render_kpi_manage(data.kpi_info);
                // self.click_setting_header_btn();
                self._set_action_move();
            });
        },

        click_setting_header_btn: function () {

            this.$el.find('.journal_manage').toggleClass('journal_header_setting');

            $(document).mouseup(function(e)
            {
                var container = $(".journal_manage");
                var setting_btn = $("#setting_header_btn");

                // if the target of the click isn't the container nor a descendant of the container
                if (!container.is(e.target) && container.has(e.target).length === 0 &&
                    !setting_btn.is(e.target) && setting_btn.has(e.target).length === 0)
                {
                    container.removeClass('journal_header_setting');
                }
            });

            this._set_action_move()
        },
        /**
         * Notifies the controller that the target has changed.
         *
         * @private
         * @param {string} target_name the name of the changed target
         * @param {string} value the new value
         */
        _notifyTargetChange: function (target_name, value) {
            this.trigger_up('dashboard_edit_target', {
                target_name: target_name,
                target_value: value,
            });
        },

        /**
         * @override
         * @private
         * @returns {Deferred}
         */
        _render: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                var data = self.state.dashboardValues;
                self._render_header(data);
            });
        },

        _render_header: function (data) {
            var self = this;
            var account_dashboard_dashboard = QWeb.render('account_dashboard.KPIDashboard', {
                widget: self,
                data: data
            });
            self.$el.prepend(account_dashboard_dashboard);
        },

        // Function render all kpis element in dashboard
        _render_kpis: function (kpi_data) {
            var self = this;
            var kpi_header = QWeb.render('account_dashboard.ElementsHeader', {
                kpi_data: kpi_data
            });
            self.$('.kpi_header').empty();
            self.$('.kpi_header').prepend(kpi_header);
        },

        // Function render kpi element in dashboard
        _render_kpi_manage: function (kpi_info) {
            var self = this;
            var kpi_header = QWeb.render('account_dashboard.JournalManage', {
                kpi_info: kpi_info
            });
            self.$('.journal_manage').empty();
            self.$('.journal_manage').prepend(kpi_header);
        },

        _set_action_move: function () {
            var self = this;
            $("ul.slides").sortable({
                placeholder: 'slide-placeholder',
                axis: "y",
                revert: 150,
                start: function(e, ui){

                    var placeholderHeight = ui.item.outerHeight();
                    ui.placeholder.height(placeholderHeight + 15);
                    $('<div class="slide-placeholder-animator" data-height="' + placeholderHeight + '"></div>')
                        .insertAfter(ui.placeholder);

                },
                change: function(event, ui) {

                    ui.placeholder.stop().height(0).animate({
                        height: ui.item.outerHeight() + 15
                    }, 300);

                    var placeholderAnimatorHeight = parseInt($(".slide-placeholder-animator").attr("data-height"));

                    $(".slide-placeholder-animator")
                        .stop()
                        .height(placeholderAnimatorHeight + 15)
                        .animate({
                            height: 0
                        }, 300, function() {
                            $(this).remove();
                            var placeholderHeight = ui.item.outerHeight();
                            $('<div class="slide-placeholder-animator" data-height="' + placeholderHeight + '"></div>')
                                .insertAfter(ui.placeholder);
                        });

                },
                stop: function(e, ui) {
                    var kpis = self.$('li.slide');
                    var kpis_name = [];
                    for (var idx = 0; idx < kpis.length; idx++){
                        var kpi = kpis[idx];
                        // kpis_name.push($(kpi).val());
                        kpis_name.push(kpi.innerText);

                    }


                    self._rpc({
                        model: 'personalized.kpi.info',
                        method: 'update_kpi_order',
                        args: [kpis_name]

                    }).then(function(data) {
                        self._render_kpis(data.kpi_data);
                    });

                    $(".slide-placeholder-animator").remove();

                },
            });
        }
    });

    var HeaderKPIsModel = KanbanModel.extend({
        /**
         * @override
         */
        init: function () {
            this.dashboardValues = {};
            this._super.apply(this, arguments);
        },

        //--------------------------------------------------------------------------
        // Public
        //--------------------------------------------------------------------------

        /**
         * @override
         */
        get: function (localID) {
            var result = this._super.apply(this, arguments);
            if (_.isObject(result)) {
                result.dashboardValues = this.dashboardValues[localID];
            }
            return result;
        },
        /**
         * @œverride
         * @returns {Deferred}
         */
        load: function () {
            return this._loadDemo(this._super.apply(this, arguments));
        },
        /**
         * @œverride
         * @returns {Deferred}
         */
        reload: function () {
            return this._loadDemo(this._super.apply(this, arguments));
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * @private
         * @param {Deferred} super_def a deferred that resolves with a dataPoint id
         * @returns {Deferred -> string} resolves to the dataPoint id
         */

        _loadDemo: function (super_def) {
            var self = this;
            var dashboard_def = this._rpc({
                model: 'personalized.kpi.info',
                method: 'kpi_header_render',
            });
            return $.when(super_def, dashboard_def).then(function(id, dashboardValues) {
                self.dashboardValues[id] = dashboardValues;
                return id;
            });
        },
    });

    var HeaderKPIsController = KanbanController.extend({
    });

    var HeaderKPIsView = KanbanView.extend({
        config: _.extend({}, KanbanView.prototype.config, {
            Model: HeaderKPIsModel,
            Renderer: HeaderKPIsRenderer,
            Controller: HeaderKPIsController,
        }),
        display_name: _lt('Dashboard'),
        icon: 'fa-dashboard',
        searchview_hidden: true,
    });

    view_registry.add('usa_kpi', HeaderKPIsView);

    return {
        Model: HeaderKPIsModel,
        Renderer: HeaderKPIsRenderer,
        Controller: HeaderKPIsController,
    };

});
