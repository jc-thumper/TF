from odoo import models, fields

NOTIFICATION_TYPE = [('all', 'All'), ('error', 'Error'), ('success', 'Success')]


class MKNotification(models.Model):
    _name = "mk.notification"
    _description = 'Marketplace Notification'

    user_id = fields.Many2one('res.users', string='Notify to')
    type = fields.Selection(NOTIFICATION_TYPE)
    is_sticky = fields.Boolean("Sticky", default=False)
    is_order_create = fields.Boolean("Order Import", default=False)
    is_product_import = fields.Boolean("Product Import", default=False)
    mk_instance_id = fields.Many2one('mk.instance', "Instance", ondelete='cascade')

    _sql_constraints = [
        ('user_id_type_unique', 'UNIQUE(user_id, type, mk_instance_id)', 'An user cannot have twice the same notification type for this marketplace.')
    ]
