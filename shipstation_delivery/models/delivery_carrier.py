import binascii
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(selection_add=[('shipstation_ts', "Shipstation")])

    shipstation_store_id = fields.Many2one('shipstation.store', 'Store', ondelete='restrict')
    shipstation_account_id = fields.Many2one(related="shipstation_store_id.account_id", string="Shipstation Account",
                                             store=True)
    use_chipest_carrier_from_multiple = fields.Boolean("Use Chipest Carrier/Service from multiple carrier?",
                                                       default=False)
    shipstation_carrier_id = fields.Many2one('shipstation.carrier', string="Carrier")
    carrier_code = fields.Char(related='shipstation_carrier_id.code', string='Carrier Code')
    shipstation_service_id = fields.Many2one('shipstation.service', string="Service")
    shipstation_package_id = fields.Many2one('shipstation.packages', string="Package")
    shipstation_insurance_provider = fields.Selection(
        [('shipsurance', 'Shipsurance Discount Insurance'), ('carrier', 'Carrier Insurance'),
         ('provider', 'Other (External)')], string="Insurance")

    def check_required_value_in_shipstation_address(self, partner, additional_fields=[]):
        missing_value = []
        mandatory_fields = ['city', 'state_id', 'country_id', 'zip']
        mandatory_fields.extend(additional_fields)
        for field in mandatory_fields:
            if not getattr(partner, field):
                missing_value.append(field)
        return missing_value

    def check_required_value_shipping_for_shipstation_request(self, orders, warehouse_address, shipping_address):
        if not warehouse_address:
            return _("Configure warehouse from Shipstation warehouse menu.")
        for order in orders:
            if not order.order_line:
                return _("You don't have any item to ship.")
            else:
                order_lines_without_weight = order.order_line.filtered(
                    lambda line_item: not line_item.product_id.type in ['service',
                                                                        'digital'] and not line_item.product_id.weight and not line_item.is_delivery)
                for order_line in order_lines_without_weight:
                    return _("Please define weight in product : \n %s") % order_line.product_id.name

            if warehouse_address and not warehouse_address.zip:
                return (_(
                    "There are some missing the values of the Warehouse address. \n Missing field(s) : Zip / Postal Code"))

            missing_value = self.check_required_value_in_shipstation_address(shipping_address)
            if missing_value:
                fields = ", ".join(missing_value)
                return (_(
                    "There are some missing the values of the Customer address. \n Missing field(s) : %s  ") % fields)

        if not self.shipstation_store_id:
            return _("Shipstation Store isn't defined delivery method.")
        return False

    def convert_ss_product_weight(self, weight):
        to_weight_uom_id = self.env.ref('uom.product_uom_oz', raise_if_not_found=False)
        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        return weight_uom_id._compute_quantity(weight, to_weight_uom_id, round=False)

    def shipstation_ts_rate_shipment(self, order):
        ss_warehouse_obj = self.env['shipstation.warehouse']
        warehouse_address = ss_warehouse_obj.search(
            [('warehouse_id', '=', order.warehouse_id.id), ('account_id', '=', self.shipstation_account_id.id)],
            limit=1).origin_address_id
        shipping_address = order.partner_shipping_id or self.partner_id
        check_value = self.check_required_value_shipping_for_shipstation_request(order, warehouse_address,
                                                                                 shipping_address)
        if check_value:
            return {'success': False, 'price': 0.0, 'error_message': check_value, 'warning_message': False}
        try:
            est_weight_value = sum([(line.product_id.weight * line.product_uom_qty) for line in
                                    order.order_line.filtered(
                                        lambda x: not x.product_id.type in ['service', 'digital'])]) or 0.0
            est_weight_value = self.convert_ss_product_weight(est_weight_value)
            # est_weight_value = est_weight_value * 35.274
            data = {
                "carrierCode": self.shipstation_carrier_id.code,
                "serviceCode": self.shipstation_service_id.code,
                "packageCode": self.shipstation_package_id.code,
                "fromPostalCode": warehouse_address.zip,
                "toState": shipping_address.state_id.code,
                "toCountry": shipping_address.country_id.code,
                "toPostalCode": shipping_address.zip,
                "toCity": shipping_address.city,
                "weight": {
                    "value": est_weight_value,
                    "units": 'ounces'
                },
                "confirmation": "delivery",
                "residential": False
            }
            if self.shipstation_package_id.is_your_packaging:
                data.update({"packageCode": 'package',
                             "dimensions":
                                 {
                                     "units": "inches",
                                     "height": self.shipstation_package_id.packaging_id.height,
                                     "length": self.shipstation_package_id.packaging_id.length,
                                     "width": self.shipstation_package_id.packaging_id.width
                                 }})
            response = self.shipstation_account_id._send_request('shipments/getrates', data, method="POST")
        except Exception as e:
            return {'success': False, 'price': 0.0, 'error_message': e, 'warning_message': False}
        if not response:
            return {'success': False, 'price': 0.0, 'error_message': "Rate Not Found!", 'warning_message': False}
        for res in response:
            shipping_charge = res.get('shipmentCost', 0.0) + res.get('otherCost', 0.0)
            return {'success': True,
                    'price': float(shipping_charge),
                    'error_message': False,
                    'warning_message': False}

    def shipstation_ts_send_shipping(self, pickings):
        res = []
        ss_warehouse_obj = self.env['shipstation.warehouse']
        for picking in pickings:
            # total_bulk_weight = picking.weight_bulk * 35.274
            total_bulk_weight = self.convert_ss_product_weight(picking.weight_bulk)
            total_value = sum([(line.product_uom_qty * line.product_id.list_price) for line in pickings.move_lines])
            warehouse_address = ss_warehouse_obj.search(
                [('warehouse_id', '=', picking.picking_type_id.warehouse_id.id),
                 ('account_id', '=', self.shipstation_account_id.id)],
                limit=1).origin_address_id
            shipping_address = picking.partner_id
            if picking.sale_id and picking.sale_id.shipstation_order_id:
                data = {
                    "orderId": picking.sale_id.shipstation_order_id,
                    "carrierCode": self.shipstation_carrier_id.code,
                    "serviceCode": self.shipstation_service_id.code,
                    "packageCode": self.shipstation_package_id.code,
                    "confirmation": 'delivery',
                    "shipDate": datetime.datetime.now().date().strftime(DEFAULT_SERVER_DATE_FORMAT),
                    "weight": {
                        "value": total_bulk_weight,
                        "units": "ounces"
                    },
                    "testLabel": True if not self.prod_environment else False
                }
            else:
                data = {
                    "carrierCode": self.shipstation_carrier_id.code,
                    "serviceCode": self.shipstation_service_id.code,
                    "packageCode": self.shipstation_package_id.code,
                    "confirmation": "delivery",
                    "shipDate": datetime.datetime.now().date().strftime(DEFAULT_SERVER_DATE_FORMAT),
                    "weight": {
                        "value": total_bulk_weight,
                        "units": 'ounces'
                    },
                    "shipFrom": {
                        "name": warehouse_address.name or '',
                        "company": warehouse_address.name if warehouse_address.is_company else '',
                        "street1": warehouse_address.street or '',
                        "street2": warehouse_address.street2 or '',
                        "city": warehouse_address.city or '',
                        "state": warehouse_address.state_id.code or '',
                        "postalCode": warehouse_address.zip or '',
                        "country": warehouse_address.country_id.code or '',
                        "phone": warehouse_address.phone or '',
                        "residential": ''
                    },
                    "shipTo": {
                        "name": shipping_address.name or '',
                        "company": shipping_address.name if shipping_address.is_company else '',
                        "street1": shipping_address.street or '',
                        "street2": shipping_address.street2 or '',
                        "city": shipping_address.city or '',
                        "state": shipping_address.state_id.code or '',
                        "postalCode": shipping_address.zip or '',
                        "country": shipping_address.country_id.code or '',
                        "phone": shipping_address.phone or '',
                        "residential": ''
                    },
                    "testLabel": True if not self.prod_environment else False
                }
            if self.shipstation_package_id.is_your_packaging:
                data.update({"packageCode": 'package',
                             "dimensions":
                                 {
                                     "units": "inches",
                                     "height": self.shipstation_package_id.packaging_id.height,
                                     "length": self.shipstation_package_id.packaging_id.length,
                                     "width": self.shipstation_package_id.packaging_id.width
                                 }})
            if self.shipstation_insurance_provider:
                data.update({"insuranceOptions":
                    {
                        "provider": self.shipstation_insurance_provider,
                        "insureShipment": True,
                        "insuredValue": total_value,
                    }})
            try:
                if picking.sale_id and picking.sale_id.shipstation_order_id:
                    response = self.shipstation_account_id._send_request('orders/createlabelfororder', data,
                                                                         method="POST")
                else:
                    response = self.shipstation_account_id._send_request('shipments/createlabel', data, method="POST")
            except Exception as e:
                raise ValidationError(e)
            if not response:
                raise ValidationError("Didn't get replay from Shipstaion")
            binary_label_data = response.get('labelData', False)
            ss_shipment_id = response.get('shipmentId')
            picking.write({'shipstation_shipment_id': ss_shipment_id})
            carrier_tracking_ref = response.get('trackingNumber')
            exact_price = float(response.get('shipmentCost'))
            binary_label_data = binascii.a2b_base64(str(binary_label_data))
            message = (("Shipment created!<br/> <b>Tracking Number : </b>%s") % (carrier_tracking_ref))
            picking.message_post(body=message,
                                 attachments=[('Shipstation-%s.%s' % (carrier_tracking_ref, "pdf"), binary_label_data)])
            shipping_data = {
                'exact_price': exact_price,
                'tracking_number': carrier_tracking_ref}
            res = res + [shipping_data]
        return res

    def shipstation_ts_cancel_shipment(self, picking):
        try:
            data = {'shipmentId': picking.shipstation_shipment_id}
            response = self.shipstation_account_id._send_request('shipments/voidlabel', data, method="POST")
            if not response.get('approved'):
                raise ValidationError(response.get('message'))
        except Exception as e:
            raise ValidationError(e)
