# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp


class DepositOrder(models.TransientModel):
    _name = 'deposit.order'
    _description = 'Deposit for Sales/Purchase Order'

    deposit_option = fields.Selection([
        ('fixed', 'By fixed amount'),
        ('percentage', 'By percentage')
    ], string='How do you want to make a deposit?', default='fixed')

    amount = fields.Float('Deposit amount', digits=dp.get_precision('Account'))

    def create_deposit(self):
        if self._context.get('active_id', False):
            active_model = self._context.get('active_model', False)
            order = self.env[active_model].browse(self._context.get('active_id'))

            amount = self.amount if self.deposit_option == 'fixed' else (self.amount * order.amount_total) / 100
            view_id = self.env.ref('account_partner_deposit.view_account_payment_deposit_order_form').id

            context = {'default_is_deposit': True,
                       'default_partner_id': order.partner_id.id,
                       'default_amount': amount,
                       'default_currency_id': order.currency_id.id,
                       }

            if active_model == 'sale.order':
                context.update({'default_payment_type': 'inbound',
                                'default_partner_type': 'customer',
                                'default_sale_deposit_id': order.id,
                                'default_property_account_customer_deposit_id': order.partner_id.property_account_customer_deposit_id.id
                                if order.partner_id.property_account_customer_deposit_id else False})
            elif active_model == 'purchase.order':
                context.update({'default_payment_type': 'outbound',
                                'default_partner_type': 'supplier',
                                'default_purchase_deposit_id': order.id,
                                'default_property_account_vendor_deposit_id': order.partner_id.property_account_vendor_deposit_id.id
                                if order.partner_id.property_account_vendor_deposit_id else False})

            return {
                'name': 'Make a Deposit',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'account.payment',
                'target': 'new',
                'view_id': view_id,
                'context': context
            }
