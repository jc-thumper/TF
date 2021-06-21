odoo.define('l10n_us_accounting.ReconciliationModel', function (require) {
    "use strict";

    let StatementModel = require('account.ReconciliationModel').StatementModel;
    const rule_fields = ['account_id', 'amount', 'amount_type', 'analytic_account_id', 'journal_id', 'label',
        'force_tax_included', 'tax_ids', 'analytic_tag_ids', 'to_check', 'amount_from_label_regex', 'decimal_separator'];

    StatementModel.include({

        /**
         * @override
         * Get account move lines for bank statement lines. If this bank statement line has no partner, use
         * suggested payee from bank rule.
         * @param handle
         * @param mode
         * @param limit
         * @returns {Promise<unknown>|*}
         * @private
         */
        _performMoveLine: function (handle, mode, limit) {
            let line = this.getLine(handle);
            let partner_id = line.st_line.partner_id;

            if (partner_id) {
                return this._super.apply(this, arguments);
            } else {
                let excluded_ids = _.map(_.union(line.reconciliation_proposition, line.mv_lines_match_rp, line.mv_lines_match_other), function (prop) {
                    return _.isNumber(prop.id) ? prop.id : null;
                }).filter(id => id != null);
                let filter = line['filter_' + mode] || "";
                limit = limit || this.limitMoveLines;

                // Get suggested payee
                partner_id = line.st_line.payee_id[0];

                return this._rpc({
                    model: 'account.reconciliation.widget',
                    method: 'get_move_lines_for_bank_statement_line',
                    args: [line.id, partner_id, excluded_ids, filter, 0, limit, mode === 'match_rp' ? 'rp' : 'other'],
                    context: this.context,
                }).then(this._formatMoveLine.bind(this, handle, mode));
            }
        },

        /**
         * @override
         * Add lines into the propositions from the reconcile model
         *
         * @see 'updateProposition' method for more informations about the
         * 'amount_type'
         *
         * @param {string} handle
         * @param {integer} reconcileModelId
         * @returns {Promise}
         */
        quickCreateProposition: async function (handle, reconcileModelId) {
            let reconcileModel = _.find(this.reconcileModels, r => r.id === reconcileModelId);
            if (!reconcileModel.has_second_line) {
                return this._super.apply(this, arguments);
            }

            // Support multi bank rule lines
            let self = this;
            let line = this.getLine(handle);
            let defs = [];
            // Get all bank rule lines in this reconciliation model.
            let ruleLines = await this._readReconciliationModelLine(reconcileModel.line_ids);

            _.each(ruleLines, function (ruleLine) {
                // Re-compute line to update current balance after applying each bank rule.
                defs.push(self._computeLine(line).then(function () {
                    // For each bank rule, create suggested line and add to line.reconciliation_proposition.
                    self._reassignBankRuleAmount(ruleLine);

                    ruleLines.payee_id = reconcileModel.payee_id;
                    let focus = self._formatQuickCreate(line, ruleLine);
                    focus.reconcileModelId = reconcileModelId;
                    line.reconciliation_proposition.push(focus);
                    self._computeReconcileModels(handle, reconcileModelId);
                }));
            });
            return Promise.all(defs).then(function () {
                let focus = self._formatQuickCreate(line, _.pick(reconcileModel, rule_fields));
                line.createForm = _.pick(focus, self.quickCreateFields);
                return self._computeLine(line);
            })
        },

        /**
         * @override
         * Add partner_id = payee if apply bank rule having suggested payee.
         * @param {Object} line
         * @param {Object} values
         * @returns {Object}
         * @private
         */
        _formatQuickCreate: function (line, values) {
            let prop = this._super.apply(this, arguments);
            prop.partner_id = values && values.payee_id ? values.payee_id[0] : false;
            return prop;
        },

        /**
         * Read bank rule lines if has_second_line = True
         * @param {list} ids
         * @private
         */
        _readReconciliationModelLine: function (ids) {
            return this._rpc({
                model: 'account.reconcile.model.line',
                method: 'read_reconciliation_model_lines',
                args: [ids]
            }).then(function (result) {
                return result;
            })
        },

        _reassignBankRuleAmount: function (rule) {
            let type = rule.amount_type;
            if (type === 'regex') {
                rule.amount_from_label_regex = rule.amount_regex;
            } else {
                rule.amount = type === 'fixed' ? rule.amount_fixed : rule.amount_percentage;
            }
        },

        /**
         * @override
         * Add payee_id to context if this bank statement line has payee_id.
         * @param {string} handle
         */
        validate: function (handle) {
            if (handle) {
                let line = this.getLine(handle);
                if (!line.st_line.partner_id && line.st_line.payee_id) {
                    this.context.payee_id = line.st_line.payee_id[0];
                }
            }
            return this._super.apply(this, arguments);
        },

        /**
         * Exclude a bank statement line, similar to validate()
         * @param handle
         */
        exclude: function (handle) {
            let line = this.getLine(handle);
            let handles = [];

            if (handle) {
                handles = [handle];
            } else {
                _.each(this.lines, function (line, handle) {
                    if (!line.reconciled && line.balance && !line.balance.amount && line.reconciliation_proposition.length) {
                        handles.push(handle);
                    }
                });
            }

            line.reconciled = true; // Actually this line is excluded but we can use this attributes as reconciled.
            this.valuemax--;        // Decrease total bank statement lines by 1.

            return this._rpc({
                model: 'account.bank.statement.line',
                method: 'action_exclude',
                args: [line.id],
                context: this.context
            }).then(function () {
                return {
                    handles: handles
                }
            })
        }
    });
});
