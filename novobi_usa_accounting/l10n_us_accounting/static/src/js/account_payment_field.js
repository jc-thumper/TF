odoo.define('usa.payment', function (require) {
    'use strict';

    let core = require('web.core');
    let field_registry = require('web.field_registry');
    let field_utils = require('web.field_utils');
    let QWeb = core.qweb;
    let AccountPayment = require('account.payment').ShowPaymentLineWidget;

    AccountPayment.include({
        /**
         * Render applied transactions and outstanding payments on invoice/bill... form.
         * @override
         * @private
         */
        _render: function () {
            let self = this;
            let info = JSON.parse(this.value);
            if (!info) {
                this.$el.html('');
                return;
            }

            _.each(info.content, function (k, v) {
                k.index = v;
                k.amount = field_utils.format.float(k.amount, {digits: k.digits});
                if (k.date) {
                    k.date = moment(k.date, 'YYYY/MM/DD').format('MMM DD, YYYY');
                }
            });
            this.$el.html(QWeb.render('ShowPaymentInfoUSA', {
                lines: info.content,
                outstanding: info.outstanding,
                title: info.title,
                type: info.type
            }));

            this.$el.find('i.remove-payment-usa').on('click', self._onRemoveMoveReconcile.bind(self));
            this.$el.find('a.open-payment-usa, a.open_transaction').on('click', self._onOpenPayment.bind(self));
        },

        /**
         * When users click on button X on applied payment to remove it.
         * By default Odoo will remove all payments paid for this transaction.
         * USA: Retrieve partial_id and pass to context to remove only this partial payment.
         * @override
         * @param {Object} event
         * @private
         */
        _onRemoveMoveReconcile: function (event) {
            let self = this;
            let paymentId = parseInt($(event.target).attr('payment-id'));
            let partialId = parseInt($(event.target).attr('partial-id'));
            if (paymentId !== undefined && !isNaN(paymentId)){
                this._rpc({
                    model: 'account.move.line',
                    method: 'remove_move_reconcile',
                    args: [paymentId],
                    context: {
                        'move_id': this.res_id,
                        'partial_id': partialId
                    },
                }).then(function () {
                    self.trigger_up('reload');
                });
            }
        },

        /**
         * Open popup to edit applied amount when users click on Outstanding payment.
         * @override
         * @param {Object} event
         * @private
         */
        _onOutstandingCreditAssign: function (event) {
            let self = this;
            let id = $(event.target).data('id') || false;

            self.do_action({
                name: 'Amount to Apply',
                type: 'ir.actions.act_window',
                res_model: 'account.invoice.partial.payment',
                views: [[false, "form"]],
                target: 'new',
                context: {
                    invoice_id: JSON.parse(this.value).move_id,
                    credit_aml_id: id
                }
            }, {
                on_close: function () {
                    self.trigger_up('reload');
                }
            });
        },

        /**
         * Action when users click on Payment/Writeoff/Credit Note name
         * @override
         * @param {Object} event
         * @private
         */
        _onOpenPayment: function (event) {
            let paymentId = parseInt($(event.target).attr('payment-id'));
            let moveId = parseInt($(event.target).attr('move-id'));
            let res_model;
            let self = this;
            let id;
            if (paymentId !== undefined && !isNaN(paymentId)){
                res_model = "account.payment";
                id = paymentId;
            } else if (moveId !== undefined && !isNaN(moveId)){
                res_model = "account.move";
                id = moveId;
            }

            let default_action = {
                type: 'ir.actions.act_window',
                res_model: res_model,
                res_id: id,
                views: [[false, 'form']],
                target: 'current'
            };

            if (res_model === "account.move" && id) {
                this._rpc({
                    model: 'account.move',
                    method: 'open_form',
                    args: [id]
                }).then(function (action) {
                    if (action) {
                        action.res_id = id;
                        self.do_action(action);
                    }
                    else
                        self.do_action(default_action);
                });
            } else if (res_model && id) {
                this.do_action(default_action);
            }
        }
    });
});