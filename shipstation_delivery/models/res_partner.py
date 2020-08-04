# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, Warning


class MarketPlacesUsernames(models.Model):
    _name = 'marketplaces.usernames'

    customer_user_id = fields.Char("Customer User ID", required=True)
    marketplace_id = fields.Many2one("shipstation.marketplace", string="Marketplace", required=True, ondelete='restrict')
    user_name = fields.Char("Username")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete='cascade')


class ResPartner(models.Model):
    _inherit = "res.partner"

    shipstation_customer_id = fields.Char("Customer ID", readonly=True)
    marketplace_usernames_ids = fields.One2many("marketplaces.usernames", "partner_id", readonly=True)
    is_shipstation_partner = fields.Boolean('Shipstation Partner', readonly=True)

    def ss_find_existing_or_create_partner(self, address_info, company, type=None):
        name = address_info.get('name', False)
        street = address_info.get('street1', False) or False
        street2 = address_info.get('street2', False) or False
        city = address_info.get('city', False)
        state_code = address_info.get('state', False)
        country_code = address_info.get('country', False)
        email = address_info.get('customerEmail', False)
        zip = address_info.get('postalCode', False)
        phone = address_info.get('phone', False)
        country_obj = self.env['res.country'].search(['|', ('code', '=', country_code), ('name', '=', country_code)],
                                                     limit=1)
        state_obj = self.env['res.country.state'].search(
            ['|', ('name', '=', state_code), ('code', '=', state_code), ('country_id', '=', country_obj.id)], limit=1)

        domain = [('name', '=', name), ('street', '=', street), ('street2', '=', street2), ('city', '=', city),
                  ('state_id', '=', state_obj.id), ('country_id', '=', country_obj.id), ('zip', '=', zip), ('phone', '=', phone), ('company_id', '=', company.id)]
        existing_partner = self.env['res.partner'].search(domain, limit=1)
        if existing_partner:
            return existing_partner
        else:
            vals = {
                'name': name,
                'parent_id': address_info.get('parent_id', False),
                'street': street,
                'street2': street2,
                'city': city,
                'state_id': state_obj.id or False,
                'country_id': country_obj.id or False,
                'phone': phone,
                'email': email,
                'zip': zip,
                'company_id': company.id,
                'type': type,
            }
            new_partner = self.env['res.partner'].create(vals)
            return new_partner

    def create_update_marketplace_usernames(self, marketplace_data):
        marketplaces_username_obj = self.env['marketplaces.usernames']
        for username in marketplace_data:
            customer_user_id = username.get('customerUserId')
            marketplace = username.get('marketplaceId')
            marketplace_id = self.env['shipstation.marketplace'].search([('marketplace_id', '=', marketplace)])
            user_name = username.get('username')
            if not marketplace_id:
                raise Warning("%s marketplace is not found!" % username.get('marketplace'))
            prepared_vals = {
                'customer_user_id': customer_user_id,
                'user_name': user_name,
                'marketplace_id': marketplace_id.id,
                'partner_id': self.id
            }
            existing_usernames = self.marketplace_usernames_ids.filtered(lambda line: line.customer_user_id == str(customer_user_id))
            if existing_usernames:
                existing_usernames.write({'user_name': user_name, 'marketplace_id': marketplace_id.id})
            else:
                marketplaces_username_obj.create(prepared_vals)
        return True

    def create_update_customers(self, customer):
        # TODO : Need to manage the company if we get the company from partner vals
        customer_id = customer.get('customerId')
        name = customer.get('name')
        company = customer.get('company')
        street = customer.get('street1')
        street2 = customer.get('street2')
        city = customer.get('city')
        state_code = customer.get('state')
        postal_code = customer.get('postalCode')
        country_code = customer.get('countryCode')
        phone = customer.get('phone')
        email = customer.get('email')
        address_verified = customer.get('addressVerified')
        country_id = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        if country_id:
            state_id = self.env['res.country.state'].search(
                [('code', '=', state_code), ('country_id', '=', country_id.id)], limit=1)
        else:
            state_id = self.env['res.country.state'].search([('code', '=', state_code)], limit=1)

        prepared_vals = {
            'name': name,
            'is_company': False,  # TODO : Need to manage the company
            # 'customer': True,
            'street': street,
            'street2': street2,
            'city': city,
            'state_id': state_id.id,
            'country_id': country_id.id,
            'zip': postal_code,
            'email': email,
            'phone': phone,
            'shipstation_customer_id': customer_id,
            'is_shipstation_partner': True
        }
        partner = self.search([('shipstation_customer_id', '=', customer_id)], limit=1)
        if partner:
            # TODO : We can added configuration for update partner if found in shipstation account
            partner.write(prepared_vals)
        else:
            domain = [
                ('name', '=ilike', name),
                ('street', '=ilike', street),
                ('street2', '=ilike', street2),
                ('city', '=ilike', city),
                ('state_id', '=', state_id.id),
                ('country_id', '=', country_id.id),
                ('zip', '=ilike', postal_code),
                ('email', '=ilike', email),
                ('phone', '=', phone)]
            partner = self.search(domain, limit=1)
            if partner:
                partner.write({
                    # 'customer': True,
                    'shipstation_customer_id': customer_id,
                    'is_shipstation_partner': True,
                })
            else:
                partner = self.create(prepared_vals)
        return partner

    @api.model
    def integrate_shipstation_customers(self, customer_data, account):
        for customer in customer_data:
            partner = self.create_update_customers(customer)
            marketplace_data = customer.get('marketplaceUsernames')
            if isinstance(marketplace_data, dict):
                partner.create_update_marketplace_usernames(marketplace_data)
        return True

    def import_customer(self, account=False):
        customers = []
        if not account:
            raise Warning("Shipstation Account not defined to import customer")
        response = account._send_request('customers?sortBy=CreateDate&sortDir=DESC&pageSize=500', {}, method='GET')
        if isinstance(response.get('customers'), dict):
            customers = [response.get('customers')]
        customers += response.get('customers')
        total_pages = response.get('pages')
        page = 2
        while total_pages:
            response = account._send_request('customers?sortBy=CreateDate&sortDir=DESC&pageSize=500&page=%s' % page, {},
                                             method='GET')
            customer_data = response.get('customers')
            if isinstance(customer_data, dict):
                customers += [customer_data]
            customers += customer_data
            total_pages -= 1
            page += 1

        if customers:
            self.integrate_shipstation_customers(customers, account)
        return True
