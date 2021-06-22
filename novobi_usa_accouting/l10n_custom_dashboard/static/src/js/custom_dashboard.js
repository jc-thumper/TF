odoo.define('l10n_custom_dashboard.custom_dashboard', function (require) {
    'use strict';

    let registry = require('web.field_registry');
    let AbstractField = require('web.AbstractField');

    let CustomDashboard = AbstractField.extend({
        className: "o_dashboard_graph w-100 h-100",
        jsLibs: [
            '/web/static/lib/Chart/Chart.js',
            '/l10n_custom_dashboard/static/lib/chartjs_plugin/chartjs-plugin-datalabels.min.js',
        ],

        init: function () {
            this._super.apply(this, arguments);
            this.graph = {};
        },

        /**
         * The widget view uses the ChartJS lib to render the graph. This lib requires that the rendering is done
         * directly into the DOM (so that it can correctly compute positions). However, the views are always rendered
         * in fragments, and appended to the DOM once ready (to prevent them from flickering). We here use the
         * on_attach_callback hook, called when the widget is attached to the DOM, to perform the rendering.
         * This ensures that the rendering is always done in the DOM.
         */
        on_attach_callback: function () {
            this._isInDOM = true;
            this._renderInDOM();
        },

        /**
         * Called when the field is detached from the DOM.
         */
        on_detach_callback: function () {
            this._isInDOM = false;
        },

        //--------------------------------------------------------------------------
        // RENDER FUNCTION
        //--------------------------------------------------------------------------

        /**
         * Render the widget only when it is in the DOM.
         *
         * @override
         * @private
         */
        _render: function () {
            if (this._isInDOM) {
                return this._renderInDOM();
            }
            return Promise.resolve();
        },


        /**
         * Render chart using Chart Js
         * @private
         */
        _renderChart: function () {
            let cssClass = '';
            let config = null;

            switch (this.graph.type) {
                case 'line':
                    cssClass = 'o_graph_linechart';
                    config = this._getLineChartConfig();
                    break;
                case 'horizontalBar':
                case 'bar':
                    cssClass = 'o_graph_barchart';
                    config = this._getBarChartConfig();
                    break;
                case 'doughnut':
                case 'pie':
                    config = this._getPieChartConfig();
            }

            let graph_view = this.$el.find('.content_kanban_view');
            graph_view.empty();
            graph_view.css('cssText', 'position: initial !important;');

            let canvas = $('<canvas/>');
            graph_view.addClass(cssClass);
            graph_view.append(canvas);
            let context = canvas[0].getContext('2d');
            this.chart = new Chart(context, config);
            // Chart.defaults.global.defaultFontSize = 11;
            Chart.defaults.global.defaultFontColor = '#333';
            Chart.plugins.unregister(ChartDataLabels);
        },

        /**
         * Get config settings for chart
         * @returns {object} settings
         * @private
         */
        _getBarChartConfig: function () {
            let self = this;
            let options = {
                layout: {
                    padding: {
                        right: this.graph.type === 'horizontalBar' ? 60 : 0,
                        left: this.graph.type === 'horizontalBar' ? 20 : 0
                    }
                },
                legend: {
                    align: 'end',
                    labels: {
                      usePointStyle: true,
                      boxWidth: 6
                    }
                },
                tooltips: {
                    /**
                     * For mixed chart (bar + line), to show line on top of bar, we need to reverse the order
                     * of data in datasets and passing reverse=True when calling get_chartjs_setting() (Python)),
                     * and also reverse the order of text in tooltip.
                     * @param tooltipModel
                     */
                    custom: (tooltipModel) => {
                        let legend = self.graph.setting.legend;
                        if (legend && legend.reverse && Array.isArray(tooltipModel.body) && Array.isArray(tooltipModel.labelColors)) {
                            tooltipModel.body.reverse();
                            tooltipModel.labelColors.reverse();
                        }
                    },
                    callbacks: {
                        title: (tooltipItems, data) => this.graph.type === 'horizontalBar' ? '' : tooltipItems[0].xLabel,
                        label: (tooltipItem, data) => {
                            let label = (data.datasets[tooltipItem.datasetIndex].label + ': ') || '';
                            let value = data.datasets[tooltipItem.datasetIndex].data[tooltipItem.index] || 0;
                            if (!self.graph.setting.no_currency) {
                                value = self._formatCurrencyValue(value);
                            }
                            return label + value;
                        }
                    }
                },
                scales: {
                    yAxes: [{
                        ticks: {
                            callback: (value, index, values) => self.graph.setting.no_currency ? value : self._formatCurrencyValue(value, 'compact')
                        }
                    }]
                },
                plugins: this.graph.type === 'horizontalBar' ? {
                    datalabels: {
                        anchor :'end',
                        align :'end',
                        formatter: (value, context) => self._formatCurrencyValue(value, 'compact')
                    }
                } : undefined
            };

            return {
                type: this.graph.type,
                data: {
                    labels: this.graph.label,
                    datasets: this.graph.data,
                },
                plugins: this.graph.type === 'horizontalBar' ? [ChartDataLabels] : undefined,
                // Merge default config vs config passed from rpc()
                options: $.extend(true, options, this.graph.setting),
            };
        },

        _getLineChartConfig: function() {
            return this._getBarChartConfig();
        },

        _getPieChartConfig: function() {
            let self = this;
            return {
                type: this.graph.type,
                data: {
                    labels: this.graph.label,
                    datasets: this.graph.data,
                },
                plugins: [ChartDataLabels],
                options: {
                    legend: {
                        align: 'end',
                        labels: {
                          usePointStyle: true,
                          boxWidth: 10
                        }
                    },
                    tooltips: {
                        callbacks: {
                            label: (tooltipItem, data) => {
                                let label = (data.labels[tooltipItem.index] + ': ') || '';
                                let value = data.datasets[tooltipItem.datasetIndex].data[tooltipItem.index] || 0;
                                let sum = data.datasets[tooltipItem.datasetIndex].data.reduce((a, b) => a + b);
                                let percentage = (value * 100 / sum).toFixed(2);
                                if (!self.graph.setting.no_currency) {
                                    value = self._formatCurrencyValue(value);
                                }
                                return label + value + ' (' + percentage + '%)';
                            }
                        }
                    },
                    plugins: {
                        datalabels: {
                            formatter: (value, ctx) => {
                                let sum = ctx.dataset.data.reduce((a, b) => a + b);
                                let percentage = (value * 100 / sum).toFixed(2);
                                return percentage > 5 ? percentage + '%' : '';
                                },
                            color: '#fff',
                        }
                    }
                },
            };
        },

        //--------------------------------------------------------------------------
        // GENERAL
        //--------------------------------------------------------------------------
        /**
         * Apply currency format before showing values on chart
         * TODO: Handle multiple currencies.
         * @param {number} value
         * @param {string} notation
         * @returns {string}
         * @private
         */
        _formatCurrencyValue: (value, notation='standard') => value.toLocaleString("en-US", {
            style: "currency",
            currency: "USD",
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
            notation: notation,
        })
    });

    registry.add("custom_graph", CustomDashboard);

    return CustomDashboard;
});