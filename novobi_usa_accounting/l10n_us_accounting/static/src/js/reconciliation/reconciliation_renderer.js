odoo.define('l10n_us_accounting.ReconciliationRenderer', function (require) {
    "use strict";

    let LineRenderer = require('account.ReconciliationRenderer').LineRenderer;
    let core = require('web.core');
    let qweb = core.qweb;

    LineRenderer.include({
        events: _.extend({}, LineRenderer.prototype.events, {
            'click .accounting_view caption .o_exclude_button button': '_onExclude',
            'click button.apply-payee': '_onClickRemovePayee',
            'click table.accounting_view td.sort': '_onSortColumn',
        }),
        /**
         * @override
         * Update tooltip for each transaction lines.
         * Show partner based on suggested payee if this line has no partner and fits that bank rule.
         * @returns {Promise|PromiseLike<any>|Promise<any>}
         */
        start: function () {
            let state = this._initialState;
            let model = _.find(state.reconcileModels, function (item) {
                return item.id === state.model_id;
            });
            let $modelName = this.$el.find('div.reconciliation_model_name');
            if (model && state.reconciliation_proposition.length > 0) {
                $modelName.css('display', 'inline-block');
                $modelName.find('span').text(model.name);
            }
            this.updateTooltipForPropositions();

            let self = this;
            state.st_line.payee_id = model ? model.payee_id : false;

            return this._super.apply(this, arguments).then(function () {
                if (state.st_line.payee_id) {
                    state.st_line.partner_id = false;
                }
                self.updateSuggestedPayee(state);
                let numOfLines = self.$el.find('table.accounting_view tbody tr.mv_line').length;
                if (numOfLines === 0) {
                    self._hideReconciliationModelName();
                }
            });
        },

        /**
         * @override
         * Handle when users click on each bank statement line, change partner, update transaction lines...
         * @param {Object} state
         */
        update: function(state) {
            // Remove Bank rule name
            let numOfLines = this.$el.find('table.accounting_view tbody tr.mv_line').length;
            this.filterBatchPayment(state);
            this._super.apply(this, arguments);
            let numOfLinesAfter = this.$el.find('table.accounting_view tbody tr.mv_line').length;
            if (numOfLinesAfter !== numOfLines) {
                this._hideReconciliationModelName();
            }
            this.updateTooltipForPropositions();
            this.updateSuggestedPayee(state);
        },

        /**
         * Odoo calls 'get_batch_payments_data' to get all un-reconciled batch payments and apply them for all BSL.
         * We need to filter them in the suggested list of each based BSL:
         *      Journal must be the same as journal of BSL
         *      Amount of batch payment <= amount of BSL
         *      If st_line.amount_currency < 0, choose OUT batch payment, else IN batch payment.
         * @param {Object} state
         */
        filterBatchPayment: function(state) {
            let relevant_payments = state.relevant_payments;

            if (relevant_payments.length > 0 && state.st_line) {
                let bsl_amount = state.st_line.amount_currency;
                let journal_id = state.st_line.journal_id;

                state.relevant_payments = relevant_payments.filter(batch =>
                    (batch.journal_id === journal_id) &&
                    (bsl_amount < 0 ? batch.type === 'outbound' && batch.amount <= -bsl_amount
                                    : batch.type === 'inbound' && batch.amount <= bsl_amount)
                )
            }
        },

        /**
         * Call api to get partner based on suggested payee and show its 'New' label.
         * @param {Object} state
         */
        updateSuggestedPayee: function(state) {
            let self = this;
            let payee = state.st_line.payee_id;

            if (payee) {
                let payee_id = payee[0];
                let payee_name = payee[1];

                this._makePartnerRecord(payee_id, payee_name).then(function (recordID) {
                    let partner = self.fields.partner_id;
                    partner.reset(self.model.get(recordID));
                    self.$el.attr('data-partner', payee_id);
                    self._toggleNewPartner(partner.$el);
                });
            }
        },

        /**
         * Show/Hide partner and its 'New' label based on suggested payee.
         * @param {jQuery} partner
         * @param {boolean} show
         * @private
         */
        _toggleNewPartner: function(partner, show=true) {
            if (partner) {
                let partner_dropdown = partner.find('.o_input_dropdown');
                if (show) {
                    partner_dropdown.find('input').addClass('apply-payee');
                    $('<button>', {
                        'class': 'badge badge-secondary apply-payee',
                        'data-toggle': 'tooltip',
                        title: "This partner is applied based on bank rule's payee condition, " +
                                    "and will not be written to bank statement line.<br/>" +
                                    "You can change or click here to remove it.",
                    })
                        .html('New')
                        .appendTo(partner_dropdown)
                        .tooltip();
                } else {
                    partner_dropdown.find('input').removeClass('apply-payee');
                    partner_dropdown.find('button.badge.badge-secondary.apply-payee').remove();
                }
            }
        },

        /**
         * When users click on button 'New' next to Partner to remove this applied partner
         * @param {event} event
         * @private
         */
        _onClickRemovePayee: function(event) {
            this._initialState.st_line.payee_id = false;
            this._hideReconciliationModelName();
            this._toggleNewPartner(this.$el.find('caption'), false);
            if (!this._initialState.st_line.partner_id) {
                this.trigger_up('change_partner', {'data': false});
            }
        },

        /**
         * @override
         * Handle if users change fields, such as partner.
         * @param {event} event
         * @private
         */
        _onFieldChanged: function (event) {
            let fieldName = event.target.name;
            if (fieldName === 'partner_id') {
                this._onClickRemovePayee(event);
            }
            this._super.apply(this, arguments);
        },

        /**
         * Exclude bank statement line.
         * @private
         */
        _onExclude: function () {
            this.trigger_up('exclude');
        },

        /**
         * Update tooltip for reconciliation propositions.
         */
        updateTooltipForPropositions: function() {
            let self = this;
            let state = this._initialState;
            let $props = this.$('.accounting_view tbody').empty();
            let props = [];
            _.each(state.reconciliation_proposition, function (prop) {
                if (prop.display) {
                    props.push(prop);
                }
            });
            _.each(props, function (line) {
                let $line = $(qweb.render("reconciliation.line.mv_line", {
                    'line': line,
                    'state': state,
                    'proposition': true
                }));
                if (!isNaN(line.id)) {
                    $('<span class="line_info_button fa fa-info-circle"/>')
                        .appendTo($line.find('.cell_info_popover'))
                        .attr("data-content", qweb.render('reconciliation.line.mv_line.details', {'line': line}));
                } else {
                    // if (typeof line.date !== 'string') {
                    //     line.date = line.date.format('MM/DD/YYYY'); // Convert date from moment object to string
                    // }
                    // Fetch account name if it is empty
                    if (line.account_id.id && !line.account_id.display_name) {
                        self._rpc({
                            model: 'account.account',
                            method: 'search_read',
                            fields: ['code', 'name'],
                            domain: [['id', '=', line.account_id.id]]
                        }).then(function(result) {
                            if (result.length) {
                                line.account_id.display_name = `${result[0].code} ${result[0].name}`;
                                $('<span class="line_info_button fa fa-info-circle"/>')
                                    .appendTo($line.find('.cell_info_popover'))
                                    .attr("data-content",
                                        qweb.render('reconciliation.line.mv_line_new.details', {'line': line}));
                            }
                        });
                    } else {
                        $('<span class="line_info_button fa fa-info-circle"/>')
                            .appendTo($line.find('.cell_info_popover'))
                            .attr("data-content",
                                qweb.render('reconciliation.line.mv_line_new.details', {'line': line}));
                    }
                }
                $props.append($line);
            });
        },

        /**
         * @override
         * Hide reconciliation model name when removing proposition line
         * @param {event} event
         * @private
         */
        _onSelectProposition: function (event) {
            this._onClickRemovePayee(event);
            this._super.apply(this, arguments);
        },

        /**
         * @override
         * Hide reconciliation model name when adding line
         * @param {event} event
         * @private
         */
        _onSelectMoveLine: function (event) {
            this._super.apply(this, arguments);
            this._hideReconciliationModelName();
        },

        /**
         * Sort suggested matching list when users click on header of table.
         * @param {event} event
         * @private
         */
        _onSortColumn: function(event) {
            // Convert string to other values
            let strDateToDate = str => $.datepicker.parseDate('mm/dd/yy', str);
            let strCurrencyToNum = str => Number(str.replace(/[^0-9.-]+/g,""));
            let strNumToNum = str => Number(str.replace(/\u200B/g,''));

            // Get string value from a cell.
            let getCellValue = (row, index) => $(row).children('td').eq(index).text().trim();

            // Get function to sort (ASC)
            let comparer = (index, sort_type) => (a, b) => {
                let valA = getCellValue(a, index);
                let valB = getCellValue(b, index);
                switch (sort_type) {
                    case 'number':
                        return strNumToNum(valA) - strNumToNum(valB);
                    case 'currency':
                        return strCurrencyToNum(valA) - strCurrencyToNum(valB);
                    case 'date':
                        return strDateToDate(valA) - strDateToDate(valB);
                    case 'text':
                        return valA.localeCompare(valB);
                }
            };

            let tables = this.$el.find('table.table_sort');
            // Suggested matching list has been displayed or not.
            let display = window.getComputedStyle(this.$el.find('.o_notebook')[0]).getPropertyValue('display');

            if (tables.length > 0 && display !== 'none') {
                let index = event.target.cellIndex;
                let sort_type = event.target.getAttribute('sort_type');
                let sort_mode = event.target.getAttribute('sort_mode') || 'asc';

                // Remove sort icon and sort mode for all headers
                let cols = this.$el.find('tr.header td.sort');
                _.each(cols, col => {
                    col.setAttribute('sort_mode', '');
                    let icon = $(col).find('span.sort_icon')[0];
                    if (icon) {
                        icon.innerHTML = '';
                    }
                });

                // Update sort icon: up arrow (ASC) or down arrow (DESC)
                let sort_icon = $(event.target).find('span.sort_icon')[0];
                if (sort_icon) {
                    sort_icon.innerHTML = sort_mode === 'desc' ? '&uarr;' : '&darr;';
                }

                // Update sort mode: 'asc' or 'desc'
                event.target.setAttribute('sort_mode', sort_mode === 'desc' ? 'asc' : 'desc');

                _.each(tables, table => {
                    // Get rows after sorting in ASC order.
                    let rows = $(table).find('tr').toArray().sort(comparer(index, sort_type));
                    // Revert rows if sorting in DESC order.
                    rows = sort_mode === 'asc' ? rows.reverse() : rows;
                    _.each(rows, row => $(table).append(row));
                })
            }
        },

        /**
         * @override
         * Hide reconciliation model name when modifying input amount
         * @param {event} event
         * @private
         */
        _editAmount: function (event) {
            this._super.apply(this, arguments);
            this._hideReconciliationModelName();
        },
        _hideReconciliationModelName: function () {
            this.$el.find('div.reconciliation_model_name').hide();
        },
    });
});