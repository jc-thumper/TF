odoo.define('l10n_us_accounting.ReconciliationClientAction', function (require) {
    "use strict";

    let StatementAction = require('account.ReconciliationClientAction').StatementAction;
    let core = require('web.core');
    let qweb = core.qweb;

    StatementAction.include({
        custom_events: _.extend({}, StatementAction.prototype.custom_events, {
            exclude: '_onExclude',
        }),
        /**
         * Render button to filter bank statement lines based on their statuses.
         * @private
         */
        _renderFilterButton: function () {
            let self = this;
            this.$filter_button = $(qweb.render('reconciliation.statement.filter_button', {widget: this.renderer}));
            this.$filter_button.find('.o_filters_menu .dropdown-item').click(function (event) {
                let isSelected = $(this).hasClass('selected');
                let filter_option = '';
                self.$filter_button.find('.o_filters_menu .dropdown-item').removeClass('selected');

                // Remove current lines
                self.$('.o_reconciliation_lines').empty();
                _.each(this.widgets, function (widget) {
                    widget.destroy();
                });
                this.widgets = [];

                if (!isSelected) {
                    filter_option = $(this).attr('data-filter');
                    $(this).toggleClass('selected');
                }

                return self.model.reload().then(function () {
                    return self._filterAndRenderLines(filter_option);
                });
            });
        },
        _filterAndRenderLines: function(filter_option) {
            let self = this;
            let linesToDisplay = this.model.getStatementLines();
            let linePromises = [];

            _.each(linesToDisplay, function (line, handle) {
                if (filter_option === 'ready' && line.balance.type <= 0) {
                    self.model.lines = _.omit(self.model.lines, handle);
                    return;
                }
                if (filter_option === 'in_need_of_action' && line.balance.type > 0) {
                    self.model.lines = _.omit(self.model.lines, handle);
                    return;
                }
                let widget = new self.config.LineRenderer(self, self.model, line);
                widget.handle = handle;
                self.widgets.push(widget);
                linePromises.push(widget.appendTo(self.$('.o_reconciliation_lines')));
            });
            if (this.model.hasMoreLines() === false) {
                this.renderer.hideLoadMoreButton(true);
            }
            else {
                this.renderer.hideLoadMoreButton(false);
            }
            return Promise.all(linePromises);
        },

        /**
         * @override
         * Insert filter dropdown button
         */
        do_show: function () {
            this._super.apply(this, arguments);
            this._renderFilterButton();
            this.updateControlPanel({
                clear: true,
                cp_content: {
                    $searchview_buttons: this.$filter_button,
                    $pager: this.$pager
                }
            });
        },

        /**
         * Exclude a bank statement line, similar to _onValidate(event)
         * @param {event} event
         * @private
         */
        _onExclude: function (event) {
            let handle = event.target.handle;
            let self = this;

            this.model.exclude(handle).then(function (result) {
                self.renderer.update({
                    'valuenow': self.model.valuenow,
                    'valuemax': self.model.valuemax,
                    'title': self.title,
                    'time': Date.now()-self.time,
                    'notifications': result.notifications,
                    'context': self.model.getContext(),
                });
                self._forceUpdate();
                _.each(result.handles, function (handle) {
                    let widget = self._getWidget(handle);
                    if (widget) {
                        widget.destroy();
                        let index = _.findIndex(self.widgets, function (widget) {
                            return widget.handle===handle;
                        });
                        self.widgets.splice(index, 1);
                    }
                });
                // Get number of widget and if less than constant and if there are more to load, load until constant
                if (self.widgets.length < self.model.defaultDisplayQty
                    && self.model.valuemax - self.model.valuenow >= self.model.defaultDisplayQty) {
                    let toLoad = self.model.defaultDisplayQty - self.widgets.length;
                    self._loadMore(toLoad);
                }
                self._openFirstLine();
            });
        }
    });
});
