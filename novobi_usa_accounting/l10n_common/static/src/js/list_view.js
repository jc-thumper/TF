odoo.define('l10n_common.list_view', function (require) {
    'use strict';

    let ListRenderer = require('web.ListRenderer');
    let field_utils = require('web.field_utils');
    let dom = require('web.dom');

    let FIELD_CLASSES_EXTEND = {
        char: 'o_list_char',
        float: 'o_list_number',
        integer: 'o_list_number',
        monetary: 'o_list_number',
        text: 'o_list_text',
        many2one: 'o_list_many2one',
        boolean: 'o_checkbox',  // Add boolean field.
    };

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

        /**
         * NOTES: Override this method to render boolean field. We just add an boolean field in model to render a checkbox.
         * Please don't use the checkbox for concurrent update. This is restricted by Odoo.
         *
         * @private
         * @param {Object} record
         * @param {Object} node
         * @param {integer} colIndex
         * @param {Object} [options]
         * @param {Object} [options.mode]
         * @param {Object} [options.renderInvisible=false]
         *        force the rendering of invisible cell content
         * @param {Object} [options.renderWidgets=false]
         *        force the rendering of the cell value thanks to a widget
         * @returns {jQuery} a <td> element
         */
        _renderBodyCell: function (record, node, colIndex, options) {
            // Copy and refactor code from Odoo.
            let tdClassName = 'o_data_cell';
            if (node.tag === 'button') {
                tdClassName += ' o_list_button';
            } else if (node.tag === 'field') {
                tdClassName += ' o_field_cell';
                let typeClass = FIELD_CLASSES_EXTEND[this.state.fields[node.attrs.name].type];
                tdClassName += typeClass ? (' ' + typeClass) : '';
                tdClassName += node.attrs.widget ? (' o_' + node.attrs.widget + '_cell') : '';
            }
            tdClassName += node.attrs.editOnly ? ' oe_edit_only' : '';
            tdClassName += node.attrs.readOnly ? ' oe_read_only' : '';

            let $td = $('<td>', { class: tdClassName, tabindex: -1 });
            let modifiers = this._registerModifiers(node, record, $td, _.pick(options, 'mode'));
            if (modifiers.invisible && !(options && options.renderInvisible)) {
                return $td;
            }

            if (node.tag === 'button') {
                return $td.append(this._renderButton(record, node));
            } else if (node.tag === 'widget') {
                return $td.append(this._renderWidget(record, node));
            }
            if (node.attrs.widget || (options && options.renderWidgets)) {
                let $el = this._renderFieldWidget(node, record, _.pick(options, 'mode'));
                return $td.append($el);
            }

            let name = node.attrs.name;
            let field = this.state.fields[name];
            let value = record.data[name];

            // Custom here
            let data = {
                data: record.data,
                escape: true,
                isPassword: 'password' in node.attrs,
                digits: node.attrs.digits && JSON.parse(node.attrs.digits),
            };
            let formattedValue = (this.editable && node.attrs.is_boolean_editable)
                ? this._formatBooleanEnable(value, field, data)
                : field_utils.format[field.type](value, field, data);

            this._handleAttributes($td, node);
            let title = field.type !== 'boolean' ? formattedValue : '';
            return $td.html(formattedValue).attr('title', title);
        },

        _formatBooleanEnable: function (value, field, options) {
            if (options && options.forceString) {
                return value ? _t('True') : _t('False');
            }
            return dom.renderCheckbox({
                prop: {
                    checked: value // In this method, we will remove disable property
                }
            });
        }
    });
});
