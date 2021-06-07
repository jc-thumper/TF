odoo.define('l10n_common.list_view', function (require) {
    'use strict';

    let ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        /**
         * Overrides to apply sticky header library (fixed label) for header of tree view.
         * @override
         */
        _renderView: function () {
            let self = this;
            return this._super.apply(this, arguments).then(function () {
                let parent = self.getParent().$el;
                // Only apply sticky header for normal list view (not one2many fields)
                let sticky = !parent.hasClass('o_field_one2many');
                let isListView = self.$el.find('table.o_list_table').length === 1;
                if (sticky && isListView) {
                    let table = self.$el.find('table.o_list_table');
                    let header = table.find('thead th');
                    let toggle = table.find('.o_optional_columns_dropdown_toggle');
                    let length = header.length;
                    for (let i = 0; i < length; i++) {
                        self._stickyElement($(header[i]), i === length - 1);
                    }
                    if (toggle) {
                        let span = $('<span>').css({
                            'position': 'absolute',
                            'top': 0,
                            'bottom': 'auto',
                            'left': 'auto',
                            'right': 0,
                            'height': '100%',
                        });
                        self._stickyElement(toggle, _,true);
                        toggle.detach().appendTo(span);
                        span.appendTo(table);
                    }
                }
            });
        },

        /**
         * Make element sticky
         * @param {jQuery} ele
         * @param {boolean} last
         * @param {boolean} transparent
         * @private
         */
        _stickyElement: function(ele, last=false, transparent=false) {
            ele.css({
                'position': 'sticky',
                'top': 0,
                'background': transparent ? 'transparent' : '#fff',
                'z-index': 1
            });
            if (last) {
                ele.css({
                    'padding-right': '30px !important',
                });
            }
        },
    });
});
