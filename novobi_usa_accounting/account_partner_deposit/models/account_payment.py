# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PaymentDeposit(models.Model):
    _inherit = 'account.payment'

    is_deposit = fields.Boolean('Is a Deposit?')
    property_account_customer_deposit_id = fields.Many2one('account.account', company_dependent=True, copy=True,
                                                           string="Customer Deposit Account",
                                                           domain=lambda self: [('user_type_id', 'in', [self.env.ref(
                                                               'account.data_account_type_current_liabilities').id]),
                                                                                ('deprecated', '=', False), ('reconcile', '=', True)])

    property_account_vendor_deposit_id = fields.Many2one('account.account', company_dependent=True, copy=True,
                                                         string="Vendor Deposit Account",
                                                         domain=lambda self: [('user_type_id', 'in', [self.env.ref(
                                                             'account.data_account_type_prepayments').id]),
                                                                              ('deprecated', '=', False), ('reconcile', '=', True)])
    deposit_ids = fields.Many2many('account.move', string='Deposit Entries')

    @api.depends('invoice_ids', 'payment_type', 'partner_type', 'partner_id')
    def _compute_destination_account_id(self):
        deposit_payments = self.filtered('is_deposit')
        for record in deposit_payments:
            if record.partner_type == 'customer':
                record.destination_account_id = record.property_account_customer_deposit_id.id
            else:
                record.destination_account_id = record.property_account_vendor_deposit_id.id

        super(PaymentDeposit, self - deposit_payments)._compute_destination_account_id()

    @api.onchange('partner_id')
    def _update_default_deposit_account(self):
        if self.partner_id and self.is_deposit:
            if self.partner_id.property_account_customer_deposit_id and self.partner_type == 'customer':
                self.property_account_customer_deposit_id = self.partner_id.property_account_customer_deposit_id.id
            elif self.partner_id.property_account_vendor_deposit_id and self.partner_type == 'supplier':
                self.property_account_vendor_deposit_id = self.partner_id.property_account_vendor_deposit_id.id

    def _compute_payment_amount(self, invoices, currency, journal, date):
        # Get default amount when create deposit from SO/PO
        if self.env.context.get('default_amount', False) and self.env.context.get('default_is_deposit', False):
            return self.env.context['default_amount']
        else:
            return super(PaymentDeposit, self)._compute_payment_amount(invoices, currency, journal, date)

    def _onchange_partner_order_id(self, order_field, state):
        # Helper function to be used in onchange for SO/PO
        if self.partner_id:
            partner_id = self.env['res.partner']._find_accounting_partner(self.partner_id).id

            # Remove SO/PO if it's from different customer
            if self[order_field] and self[order_field].partner_id.commercial_partner_id.id != partner_id:
                self[order_field] = False

            return {'domain': {order_field: [('partner_id.commercial_partner_id', '=', partner_id),
                                             ('state', 'in', state)]}
                    }
        else:
            self[order_field] = False

    def _validate_order_id(self, order_field, model_name):
        # Helper function to be used for validating before post
        for payment in self:
            partner_id = self.env['res.partner']._find_accounting_partner(payment.partner_id).id
            if payment[order_field] and payment[order_field].partner_id.commercial_partner_id.id != partner_id:
                raise ValidationError(_("The %s's customer does not match with the deposit's.") % model_name)

    def action_draft(self):
        super().action_draft()

        # Cancel, remove deposit from invoice and delete deposit moves
        moves = self.mapped('deposit_ids')
        moves.filtered(lambda move: move.state == 'posted').button_draft()
        moves.with_context(force_delete=True).unlink()

    @api.depends('partner_id', 'currency_id')
    def _get_has_open_invoice(self):
        """
        override
        :return:
        """
        for record in self:
            record.has_open_invoice = False

            if record.is_deposit:
                continue

            super(PaymentDeposit, record)._get_has_open_invoice()
