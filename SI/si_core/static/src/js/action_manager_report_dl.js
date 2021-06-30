odoo.define('si_core.ActionManager', function (require) {
"use strict";

/**
 * The purpose of this file is to add the support of Odoo actions of type
 * 'ir_actions_report_download' to the ActionManager.
 */

let ActionManager = require('web.ActionManager'),
    crash_manager = require('web.crash_manager'),
    framework = require('web.framework'),
    session = require('web.session');

ActionManager.include({
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Executes actions of type 'ir_actions_report_download'.
     *
     * @private
     * @param {Object} action the description of the action to execute
     * @returns {Deferred} resolved when the report has been downloaded ;
     *   rejected if an error occurred during the report generation
     */
    _executeReportDownloadAction: function (action) {
        framework.blockUI();
        let def = $.Deferred();
        session.get_file({
            url: '/get_reports',
            data: action.data,
            success: def.resolve.bind(def),
            error: function () {
                crash_manager.rpc_error.apply(crash_manager, arguments);
                def.reject();
            },
            complete: framework.unblockUI,
        });
        return def;
    },
    /**
     * Overrides to handle the 'ir_actions_report_download' actions.
     *
     * @override
     * @private
     */
    _handleAction: function (action, options) {
        if (action.type === 'ir_actions_report_download') {
            if (action.data.options === ""){
                action.data.options = "{}";
            }
            let opt = JSON.parse(action.data.options);
            opt.tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
            action.data.options = JSON.stringify(opt);

            return this._executeReportDownloadAction(action, options);
        }
        return this._super.apply(this, arguments);
    },
});

});
