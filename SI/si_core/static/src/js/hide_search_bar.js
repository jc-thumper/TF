odoo.define('si_core.HideSearchBar', function (require) {
    "use strict";

    let ControlPanel = require('web.ControlPanel');

    ControlPanel.include({
        _getParentAction: function(){
            let parent = this.getParent(),
                controllerStack = parent.controllerStack,
                controller =  controllerStack[controllerStack.length - 1],
                actionID = parent.controllers[controller].actionID;

            return parent.actions[actionID];
        },

        _render_breadcrumbs_li: function (bc, index, length) {
            let $bc = this._super.apply(this, arguments),
                action = this._getParentAction(),
                context = action.context;

            if (context.hide_right_cp){
                this.$el.find('.o_cp_searchview').css('visibility', 'hidden');
                this.$el.find('.o_cp_right').css('visibility', 'hidden');
            } else {
                this.$el.find('.o_cp_searchview').css('visibility', 'visible');
                this.$el.find('.o_cp_right').css('visibility', 'visible');
            }

            return $bc;
        },
    });

});
