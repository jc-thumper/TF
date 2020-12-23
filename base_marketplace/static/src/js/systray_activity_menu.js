odoo.define('base_marketplace.SystrayItem', function (require) {
    "use strict";

    var core = require('web.core');
    var session = require('web.session');
    var SystrayMenu = require('web.SystrayMenu');
    var Widget = require('web.Widget');
    var QWeb = core.qweb;

    /**
     * Menu item appended in the systray part of the navbar.
     */
    var MarketplaceMenu = Widget.extend({
        name: 'marketplace_menu',
        template: 'base_marketplace.SystrayItem',
        events: {
            'click .o_mail_activity_action': '_onActivityActionClick',
            'click .o_mail_preview': '_onMarketplaceFilterClick',
            'show.bs.dropdown': '_onMarketplaceMenuShow',
        },
        start: function () {
            this._$marketplacePreview = this.$('.o_mail_systray_dropdown_items');
            this._updateMarketplacePreview();
            return this._super();
        },
        //--------------------------------------------------
        // Private
        //--------------------------------------------------
        /**
         * Make RPC and get marketplaces details
         * @private
         */
        _getMarketplaceData: function () {
            var self = this;

            return self._rpc({
                model: 'mk.instance',
                method: 'systray_get_marketplaces',
                args: [],
                kwargs: {context: session.user_context},
            }).then(function (data) {
                self._marketplaces = data;
            });
        },

        /**
         * Update(render) activity system tray view on activity updation.
         * @private
         */
        _updateMarketplacePreview: function () {
            var self = this;
            self._getMarketplaceData().then(function () {
                self._$marketplacePreview.html(QWeb.render('mail.systray.MarketplaceMenu.Previews', {
                    marketplaces: self._marketplaces
                }));
            });
        },

        //------------------------------------------------------------
        // Handlers
        //------------------------------------------------------------

        /**
         * Redirect to marketplace instance view
         * @private
         * @param {MouseEvent} event
         */
        _onMarketplaceFilterClick: function (event) {
            // fetch the data from the button otherwise fetch the ones from the parent (.o_mail_preview).
            var data = _.extend({}, $(event.currentTarget).data(), $(event.target).data());
            this.do_action({
                type: 'ir.actions.act_window',
                name: data.model_name,
                res_model: data.res_model,
                views: [[false, 'kanban'], [false, 'form']],
                search_view_id: [false],
                domain: [['id', '=', data.id]],
            });
        },
        /**
         * @private
         */
        _onMarketplaceMenuShow: function () {
            this._updateMarketplacePreview();
        },

    });

    session.user_has_group('base_marketplace.group_base_marketplace_manager').then(function (has_group) {
        if (has_group) {
            SystrayMenu.Items.push(MarketplaceMenu);
        }
    });

    return MarketplaceMenu;

});
