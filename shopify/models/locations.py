from .. import shopify
from odoo import models, fields


class ShopifyAccount(models.Model):
    _name = "shopify.location.ts"
    _description = 'Shopify Location'

    name = fields.Char('Account Name', required=True)
    shopify_location_id = fields.Char("Shopify Location ID", copy=False)
    mk_instance_id = fields.Many2one('mk.instance', "Instance", ondelete='cascade')
    is_default_location = fields.Boolean("Is Default Location?",
                                         help="Location that Shopify and apps will use when no other location is specified. Only locations that fulfill online orders can be used as your default location.",
                                         copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse')
    location_id = fields.Many2one('stock.location', 'Location')
    partner_id = fields.Many2one('res.partner', 'Customer')
    is_legacy = fields.Boolean('Is Legacy Location')

    def prepare_domain_for_location_partner(self, vals, location):
        domain = [('name', '=', vals.get('name'))]
        address1 = location.get('address1')
        address2 = location.get('address2')
        city = location.get('city')
        country = location.get('country')
        country_code = location.get('country_code')
        phone = location.get('phone')
        province = location.get('province')
        province_code = location.get('province_code')
        zip = location.get('zip')
        state_id = self.env['res.country.state'].search(
            ['|', ('code', '=', province_code), ('name', '=', province)], limit=1)
        country_id = self.env['res.country'].search(
            ['|', ('code', '=', country_code), ('name', '=', country)], limit=1)

        partner_vals = {}
        address1 and domain.append(('street', '=', address1)) and partner_vals.update({'street': address1})
        address2 and domain.append(('street2', '=', address2)) and partner_vals.update({'street2': address2})
        state_id and domain.append(('state_id', '=', state_id.id)) and partner_vals.update({'state_id': state_id.id})
        country_id and domain.append(('country_id', '=', country_id.id)) and partner_vals.update(
            {'country_id': country_id.id})
        city and domain.append(('city', '=', city)) and partner_vals.update({'city': city})
        phone and domain.append(('phone', '=', phone)) and partner_vals.update({'phone': phone})
        zip and domain.append(('zip', '=', zip)) and partner_vals.update({'zip': zip})
        return domain, partner_vals

    def prepare_vals_for_location(self, location, mk_instance_id):
        partner_obj = self.env['res.partner']
        vals = {}
        vals.update({'name': location.get('name')})
        vals.update({'shopify_location_id': location.get('id')})
        vals.update({'mk_instance_id': mk_instance_id.id})
        vals.update({'is_legacy': location.get('legacy')})
        domain, partner_vals = self.prepare_domain_for_location_partner(vals, location)
        partner_id = partner_obj.search(domain, limit=1)
        if partner_id:
            vals.update({'partner_id': partner_id.id})
        else:
            partner_vals.update({'name': vals.get('name')})
            partner_id = partner_obj.create(partner_vals)
            vals.update({'partner_id': partner_id.id})
        return vals

    def set_default_location(self, mk_instance_id):
        shopify_default_location = self.search([('is_default_location', '=', True), ('mk_instance_id', '=', mk_instance_id.id)], limit=1)
        if shopify_default_location:
            shopify_default_location.write({'is_default_location': False})
        default_location_id = shopify.Shop.current().to_dict().get('primary_location_id')
        default_location = default_location_id and self.search([('shopify_location_id', '=', default_location_id), ('mk_instance_id', '=', mk_instance_id.id)]) or False
        if default_location:
            default_location.write({'is_default_location': True,
                                    'warehouse_id': mk_instance_id.warehouse_id.id,
                                    'location_id': mk_instance_id.warehouse_id.lot_stock_id.id})
        return True

    def import_location_from_shopify(self, mk_instance_id):
        mk_instance_id.connection_to_shopify()
        shopify_locations = shopify.Location.find(active=True)
        for location in shopify_locations:
            location = location.to_dict()
            vals = self.prepare_vals_for_location(location, mk_instance_id)
            shopify_location_id = self.search([('shopify_location_id', '=', location.get('id')), ('mk_instance_id', '=', mk_instance_id.id)])
            if shopify_location_id:
                shopify_location_id.write(vals)
            else:
                self.create(vals)
        self.set_default_location(mk_instance_id)
        return True
