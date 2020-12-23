from odoo import models, fields, api, _
import base64
import hashlib
import requests
import logging

_logger = logging.getLogger("Teqstars:Base Marketplace")


class ListingImage(models.Model):
    _name = 'mk.listing.image'
    _description = 'Listing Image'
    _order = 'sequence, id'

    @api.depends('image')
    def get_image_hex(self):
        for record in self:
            record.image_hex = hashlib.md5(record.image).hexdigest() if record.image else False

    name = fields.Char('Name')
    sequence = fields.Integer(help='Sequence', index=True, default=10)
    image = fields.Binary('Image', attachment=True)
    url = fields.Char('Image URL')
    image_hex = fields.Char('Image Hex', compute='get_image_hex', store=True, help="Technical field to identify the duplicate image")
    mk_id = fields.Char("Marketplace Identification", copy=False)
    mk_listing_id = fields.Many2one('mk.listing', 'Related Listing', copy=False)
    mk_instance_id = fields.Many2one('mk.instance', string='Marketplace', related='mk_listing_id.mk_instance_id', store=True)
    marketplace = fields.Selection(related="mk_instance_id.marketplace", string='Marketplace Name')
    mk_listing_item_ids = fields.Many2many('mk.listing.item', 'mk_listing_image_listing_rel', 'mk_listing_image_id', 'listing_item_id', string="Related Listing Item")

    @api.onchange('url')
    def _onchange_url(self):
        if not self.url:
            self.image = False
            return {}
        image_types = ["image/jpeg", "image/png", "image/tiff", "image/vnd.microsoft.icon", "image/x-icon", "image/vnd.djvu", "image/svg+xml", "image/gif"]
        try:
            response = requests.get(self.url, stream=True, verify=False, timeout=10)
            if response.status_code == 200:
                if response.headers["Content-Type"] in image_types:
                    image = base64.b64encode(response.content)
                    self.image = image
        except:
            self.image = False
            warning = {}
            title = _("Warning for : {}".format(self.mk_listing_id.name))
            warning['title'] = title
            warning['message'] = "There seems to problem while fetching Image from URL"
            return {'warning': warning}
        return {}

    @api.model
    def create(self, vals):
        res = super(ListingImage, self).create(vals)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/marketplace/product/image/{}/{}'.format(self.env.cr.dbname, base64.urlsafe_b64encode(str(res.id).encode("utf-8")).decode("utf-8"))
        if res.mk_listing_item_ids and not res.mk_listing_id:
            res.write({'mk_listing_id': res.mk_listing_item_ids.mapped('mk_listing_id') and res.mk_listing_item_ids.mapped('mk_listing_id')[0].id or False})
        res.write({'url': url})
        return res
