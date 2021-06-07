odoo.define('dashboard_alert.alert', function (require) {
    'use strict';

    /**
     * This file defines the US Accounting Dashboard view (alongside its renderer, model
     * and controller), extending the Kanban view.
     * The US Accounting Dashboard view is registered to the view registry.
     * A large part of this code should be extracted in an AbstractDashboard
     * widget in web, to avoid code duplication (see SalesTeamDashboard).
     */

    var HeaderKPIsRenderer = require('account_dashboard.kpi_header').Renderer;
    var core = require('web.core');

    var _t = core._t;

    HeaderKPIsRenderer.include({
        events:  _.extend({}, HeaderKPIsRenderer.prototype.events, {
            'click .alert-bell': 'click_alert_bell_btn',
        }),
        //--------------------------------------------------------------------------
        // EVENTS
        //--------------------------------------------------------------------------
        click_alert_bell_btn: function (event) {
            var elem = $(event.currentTarget);
            var name_elem = $(elem[0].offsetParent).find('.kpi_name')[0].innerText;
            var index_elem = $.map(this.$el.find('.kpi_name'),
                function(e) {
                    return e.innerText
                }).findIndex(fruit => fruit === name_elem);
            var kpi_id = parseInt(this.$el.find('.kpi_id')[index_elem].innerText);
            this.do_action({
                    name: _t('Alert for ' + name_elem),
                    type: 'ir.actions.act_window',
                    res_model: 'alert.info',
                    context: {
                        'search_default_active_self_created': 1,
                        'default_kpi_id': kpi_id,
                    },
                    domain: [['kpi_id', '=', kpi_id]],
                    views: [[false, 'list'], [false, 'form']],
                    view_mode: "list",
                    target: 'current',
                })
        },

        reinitialize: function (value) {
            this.isDirty = false;
            this.floating = false;
            return value;
        },

    });
    return HeaderKPIsRenderer;
});
