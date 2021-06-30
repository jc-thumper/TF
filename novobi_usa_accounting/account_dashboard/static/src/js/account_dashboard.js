odoo.define('account_dashboard.account_dashboard', function (require) {
    'use strict';

    let registry = require('web.field_registry');
    let core = require('web.core');
    let qweb = core.qweb;
    let CustomDashboard = require('l10n_custom_dashboard.custom_dashboard');

    let AccountDashboard = CustomDashboard.extend({
        className: "o_dashboard_graph o_journal w-100 h-100",
        events:{
            'change select': '_changeSelection',
        },

        /**
         * Function to call rpc to retrieve data from model.
         * @param data
         * @param default_param
         * @private
         */
        _retrieveModelData: function(data, default_param) {
            let self = this;
            this._rpc({
                method: data.function_retrieve,
                model: this.model,
                args: default_param.concat(data.extra_param)
            }).then(function (result) {
                self._getData(data.data_type, result);
                self._renderChart();
                self._renderInfo();
            });
        },

        _getData: function(type, data) {
            if (data.constructor === Object) {
                this.graph = {
                    type: type,
                    label: data.label,
                    data: data.data,
                    setting: data.setting,
                };
                this.info = data.info_data;
            }
        },

        /**
         * Render the widget. This function assumes that it is attached to the DOM.
         *
         * @private
         */
        _renderInDOM: function () {

            if (this.value) {
                let data = JSON.parse(this.value)[0];
                this.selection = data.selection;

                this._renderSelection(data);

                let range = this._getRangePeriod();
                let default_param = [range.start_date, range.end_date, range.date_separate];

                if (data.function_retrieve === '') {
                    this._getData(data.data_type, data);
                    this._renderChart();
                } else {
                    this._retrieveModelData(data, default_param);
                }
            }
        },

        /**
         * Render selection on top of chart
         * @param {dict} data
         * @private
         */
        _renderSelection: function(data) {
            if (this.$el.find('.journal_info').length === 0) {
                $(qweb.render('JournalDataItemView', {
                    'type': data.name,
                    'data': data
                })).appendTo($(this.$el).empty());
            }
        },

        /**
         * Render information part on top of chart.
         * @private
         */
        _renderInfo: function () {
            let info_view = this.$el.find('.info-view');
            info_view.empty();
            $(qweb.render('InfoView', {
                'info': this.info
            })).appendTo(info_view);
        },

        /**
         * Function to re-render after users change value of selection.
         * @private
         */
        _changeSelection: function() {
            this._renderInDOM();
        },

        /**
         * Get information about the range time and type of period chosen in the
         * selection field.
         *
         * @private
         */
        _getRangePeriod: function () {
            let selection = this.$el.find('select#Period')[0];
            let return_value = {};

            if (selection !== undefined) {
                let selected_value = this.$el.find('select#Period')[0].value;
                for (let i in this.selection){
                    let item = this.selection[i];
                    if (item.n === selected_value) {
                        return_value.start_date = item.s;
                        return_value.end_date = item.e;
                        return_value.date_separate = item.k;
                    }
                }
            }
            return return_value;
        },
    });

    registry.add("journal_data", AccountDashboard);

    return AccountDashboard;
});