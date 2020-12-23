odoo.define('base_marketplace.backend_mk_general_dashboard', function (require) {
    'use strict';

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var datepicker = require('web.datepicker');
    var QWeb = core.qweb;
    var session = require('web.session');
    var field_utils = require('web.field_utils');

    var Dashboard = AbstractAction.extend({
        hasControlPanel: true,
        contentTemplate: 'base_marketplace.DashboardMain',

        jsLibs: [],
        cssLibs: [],

        init: function (parent, menu, params, action) {
            this._super(parent, menu, params, action);
            this.mk_instance_id = menu.context.active_id;
            this.dashboards_templates = ['base_marketplace.dashboard_body'];
        },

        willStart: function () {
            var self = this;
            var extra_info = this._rpc({
                model: 'mk.instance',
                method: 'get_mk_dashboard_informations',
                args: [1, self.report_options],
            }).then(function (result) {
                return self.parse_mk_dashboard_informations(result);
            });
            return $.when(extra_info, this._super()).then(function () {
                return self.fetch_data();
            });
        },

        start: function () {
            var self = this;
            var extra_info = this._rpc({
                model: 'mk.instance',
                method: 'get_mk_dashboard_informations',
                args: [1, self.report_options],
            }).then(function (result) {
                return self.parse_mk_dashboard_informations(result);
            });
            return $.when(extra_info, this._super.apply(this, arguments)).then(function () {
                self.render();
                self.render_dashboards();
                self._render_charts();
            });
        },

        reload: function () {
            var self = this;
            return this._rpc({
                model: 'mk.instance',
                method: 'get_mk_dashboard_informations',
                args: [1, self.report_options],
            }).then(function (result) {
                self.parse_mk_dashboard_informations(result);
                $.when(self.fetch_data()).then(function () {
                    self.render();
                    self.render_dashboards();
                    return self._render_charts();
                });
            });
        },

        parse_mk_dashboard_informations: function (values) {
            this.report_options = values.options;
            this.$searchview_buttons = $(values.searchview_html);
        },

        on_reverse_breadcrumb: function () {
            var self = this;
            self.update_cp();
            $.when(this.fetch_data()).then(function () {
                self.render_dashboards();
                self._render_charts();
            });
        },

        // renderButtons: function () {
        //     var self = this;
        //     this.$buttons = $(QWeb.render("base_marketplace.buttons", {buttons: this.buttons}));
        //     // bind actions
        //     _.each(this.$buttons.siblings('button'), function (el) {
        //         $(el).click(function () {
        //             self.$buttons.attr('disabled', true);
        //             return self._rpc({
        //                 model: self.report_model,
        //                 method: $(el).attr('action'),
        //                 args: [self.financial_id, self.report_options],
        //                 context: self.odoo_context,
        //             })
        //                 .then(function (result) {
        //                     return self.do_action(result);
        //                 })
        //                 .always(function () {
        //                     self.$buttons.attr('disabled', false);
        //                 });
        //         });
        //     });
        //     return this.$buttons;
        // },

        render: function () {
            this.render_searchview_buttons();
            this.update_cp();
        },

        render_searchview_buttons: function () {
            var self = this;
            // bind searchview buttons/filter to the correct actions
            var $datetimepickers = this.$searchview_buttons.find('.js_mk_reports_datetimepicker');
            var options = { // Set the options for the datetimepickers
                locale: moment.locale(),
                format: 'L',
                icons: {
                    date: "fa fa-calendar",
                },
            };
            // attach datepicker
            $datetimepickers.each(function () {
                var name = $(this).find('input').attr('name');
                var defaultValue = $(this).data('default-value');
                $(this).datetimepicker(options);
                var dt = new datepicker.DateWidget(options);
                dt.replace($(this)).then(function () {
                    dt.$el.find('input').attr('name', name);
                    if (defaultValue) { // Set its default value if there is one
                        dt.setValue(moment(defaultValue));
                    }
                });
            });
            // format date that needs to be show in user lang
            _.each(this.$searchview_buttons.find('.js_format_date'), function (dt) {
                var date_value = $(dt).html();
                $(dt).html((new moment(date_value)).format('ll'));
            });
            // fold all menu
            this.$searchview_buttons.find('.js_foldable_trigger').click(function (event) {
                $(this).toggleClass('o_closed_menu o_open_menu');
                self.$searchview_buttons.find('.o_foldable_menu[data-filter="' + $(this).data('filter') + '"]').toggleClass('o_closed_menu');
            });
            // render filter (add selected class to the options that are selected)
            _.each(self.report_options, function (k) {
                if (k !== null && k.filter !== undefined) {
                    self.$searchview_buttons.find('[data-filter="' + k.filter + '"]').addClass('selected');
                }
            });
            // click event
            this.$searchview_buttons.find('.js_mk_report_date_filter').click(function (event) {
                self.report_options.date.filter = $(this).data('filter');
                var error = false;
                if ($(this).data('filter') === 'custom') {
                    var date_from = self.$searchview_buttons.find('.o_datepicker_input[name="date_from"]');
                    var date_to = self.$searchview_buttons.find('.o_datepicker_input[name="date_to"]');
                    if (date_from.length > 0) {
                        error = date_from.val() === "" || date_to.val() === "";
                        self.report_options.date.date_from = field_utils.parse.date(date_from.val());
                        self.report_options.date.date_to = field_utils.parse.date(date_to.val());
                    } else {
                        error = date_to.val() === "";
                        self.report_options.date.date = field_utils.parse.date(date_to.val());
                    }
                }
                if (error) {
                    crash_manager.show_warning({data: {message: _t('Date cannot be empty')}});
                } else {
                    self.reload();
                }
            });
        },

        // Updates the control panel and render the elements that have yet to be rendered
        update_cp: function () {
            var status = {
                cp_content: {
                    $searchview_buttons: this.$searchview_buttons,
                    $pager: this.$pager,
                    $searchview: this.$searchview
                },
            };
            this.updateControlPanel(status,{
                clear: true,
            });
        },

        render_dashboards: function () {
            var self = this;
            self.$('.o_ts_dashboard_content').empty();
            _.each(this.dashboards_templates, function (template) {
                self.$('.o_ts_dashboard_content').append(QWeb.render(template, {widget: self}));
            });
        },

        /**
         * Fetches dashboard data
         */
        fetch_data: function () {
            var self = this;
            return this._rpc({
                route: '/base_marketplace/get_dashboard_data',
                params: {
                    mk_instance_id: this.mk_instance_id,
                    date_from: this.report_options["date"]['date_from'],
                    date_to: this.report_options["date"]['date_to'],
                }
            }).then(function (result) {
                self.data = result.dashboards;
                self.refresh_interval = result.refresh_interval;
                self.currency_id = self.data.currency_id
            });
        },

        render_monetary_field: function (value, currency_id) {
            var currency = session.get_currency(currency_id);
            var formatted_value = field_utils.format.float(value || 0, {digits: currency && currency.digits});
            if (currency) {
                if (currency.position === "after") {
                    formatted_value += currency.symbol;
                } else {
                    formatted_value = currency.symbol + formatted_value;
                }
            }
            return formatted_value;
        },

        render_line_chart: function (sales_chart) {
            var series = this.data.sale_graph.series;
            var categories = this.data.sale_graph.categories;
            var options = {
                series: series,
                chart: {
                    height: 350,
                    type: 'line',
                },
                grid: {
                    show: false,
                },
                stroke: {
                    width: 7,
                    curve: 'smooth'
                },
                yaxis: {
                    title: {
                        text: 'Amount',
                    },
                    labels: {
                        formatter: function (value) {
                            return self.render_monetary_field(value, self.currency_id);
                        }
                    },
                },
                xaxis: {
                    type: 'datetime',
                    categories: categories,
                },
                title: {
                    text: 'Total Selling',
                    align: 'left',
                    style: {
                        fontSize: "16px",
                        color: '#666'
                    }
                },
                markers: {
                    // size: 4,
                    colors: ["#FFA41B"],
                    strokeColors: "#fff",
                    strokeWidth: 2,
                    hover: {
                        size: 7,
                    }
                }
            };

            var chart = new ApexCharts(sales_chart[0], options);
            chart.render();
        },

        render_pie_chart: function (pie_chart, country_graph) {
            var series = country_graph.series;
            var labels = country_graph.labels;
            var options = {
                series: series,
                chart: {
                    width: 430,
                    // height:415,
                    type: 'pie',
                },
                labels: labels,
                legend: {
                    position: 'bottom',
                    horizontalAlign: 'center',
                },
                yaxis: {
                    labels: {
                        formatter: function (value) {
                            return self.render_monetary_field(value, self.currency_id);
                        }
                    },
                },
            };

            var chart = new ApexCharts(pie_chart[0], options);
            chart.render();
        },

        render_instance_bar_chart: function (bar_chart, bar_chart_data) {
            var series = bar_chart_data.series;
            var categories = bar_chart_data.categories;
            var options = {
                title: {
                    text: 'Instance wise Selling',
                    align: 'left',
                    style: {
                        fontSize: "16px",
                        color: '#666'
                    }
                },
                chart: {
                    height: 350,
                    type: 'bar',
                },
                grid: {
                    show: false,
                },
                plotOptions: {
                    bar: {
                        horizontal: true,
                        distributed: true
                    },
                },
                series: series,
                xaxis: {
                    categories: categories,
                    title: {
                        text: 'Amount',
                    },
                    labels: {
                        formatter: function (value) {
                            return self.render_monetary_field(value, self.currency_id);
                        }
                    },
                },
                legend: {
                    show: false
                },
                dataLabels: {
                    formatter: function (value, opts) {
                        return self.render_monetary_field(value, self.currency_id);
                    },
                }
            };

            var chart = new ApexCharts(bar_chart[0], options);
            chart.render();
        },

        _render_charts: function () {
            self = this;
            var sales_chart = self.$el.find("#chart");
            var pie_chart = self.$el.find("#pieChart");
            var category_pie_chart = self.$el.find("#category_pie_chart");
            var bar_chart = self.$el.find("#bar_chart");
            var mk_revenue_pieChart = self.$el.find("#mk_revenue_pieChart");
            var category_graph = self.data.category_graph;
            var country_graph = self.data.country_graph;
            var bar_chart_data = self.data.bar_graph;
            var mk_revenue_pieChart_data = self.data.mk_revenue_pieChart;
            if (self.data.sale_graph.categories && self.data.sale_graph.series) {
                self.render_line_chart(sales_chart);
            } else {
                sales_chart.append($('<h3 style="text-align: center;padding-top: 170px;color: #747874">').text("No data to display!!!"));
            }
            if (country_graph && country_graph.labels && country_graph.series) {
                self.render_pie_chart(pie_chart, country_graph);
            } else {
                pie_chart.append($('<h3 style="text-align: center;padding-top: 123px;color: #747874">').text("No data to display!!!"));
            }
            if (category_graph && category_graph.labels && category_graph.series) {
                self.render_pie_chart(category_pie_chart, category_graph);
            } else {
                category_pie_chart.append($('<h3 style="text-align: center;padding-top: 123px;color: #747874">').text("No data to display!!!"));
            }
            if (bar_chart_data && bar_chart_data.categories && bar_chart_data.series) {
                self.render_instance_bar_chart(bar_chart, bar_chart_data);
            } else {
                bar_chart.append($('<h3 style="text-align: center;padding-top: 170px;color: #747874">').text("No data to display!!!"));
            }
            if (mk_revenue_pieChart_data && mk_revenue_pieChart_data.labels && mk_revenue_pieChart_data.series) {
                self.render_pie_chart(mk_revenue_pieChart, mk_revenue_pieChart_data);
            } else {
                mk_revenue_pieChart.append($('<h3 style="text-align: center;padding-top: 170px;color: #747874">').text("No data to display!!!"));
            }
            window.dispatchEvent(new Event('resize'));
        }
    });
    core.action_registry.add('backend_mk_general_dashboard', Dashboard);
    return Dashboard;
});
