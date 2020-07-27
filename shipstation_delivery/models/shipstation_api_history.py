from odoo import models, fields, api


class ShipstationAPIHistory(models.Model):
    _name = 'shipstation.api.history'
    _order = 'id desc'
    _description = 'API History'

    name = fields.Char("Name")
    create_date = fields.Datetime("Create Date")
    account_id = fields.Many2one('shipstation.accounts', string="Account")
    transaction_log_ids = fields.One2many("shipstation.transaction.log", "job_id", string="Log")
    skip_process = fields.Boolean("Skip Process")
    application = fields.Selection([('sales', 'Sales')
                                       , ('sync_products', 'Sync Products')
                                       , ('product', 'Product')
                                       , ('price', 'Price')
                                       , ('other', 'Other')], string="Application")
    operation_type = fields.Selection([('import', 'Import'), ('export', 'Export')], string="Operation")
    message = fields.Text("Message")

    @api.model
    def create(self, vals):
        vals.update({'name': self.env.ref('shipstation_delivery.seq_shipstation_api_history')._next()})
        res = super(ShipstationAPIHistory, self).create(vals)
        return res


class ShipstationAPIHistoryLine(models.Model):
    _name = 'shipstation.api.history.line'
    _order = 'id desc'
    _description = 'API History Lines'

    message = fields.Text("Message")
    model_id = fields.Many2one("ir.model", string="Model")
    res_id = fields.Integer("Record ID")
    job_id = fields.Many2one("shipstation.api.history", string="History")
    log_type = fields.Selection([
        ('not_found', 'NOT FOUND'),
        ('mismatch', 'MISMATCH'),
        ('error', 'Error'),
        ('warning', 'Warning')
    ], 'Log Type')
    action_type = fields.Selection([
        ('create', 'Created New'),
        ('skip_line', 'Line Skipped'),
        ('terminate_process_with_log', 'Terminate Process With Log')
    ], 'Action')
    operation_type = fields.Selection([('import', 'Import'), ('export', 'Export')]
                                      , string="Operation", related="job_id.operation_type", store=False, readonly=True)
    not_found_value = fields.Char('Not Founded Value')
    manually_processed = fields.Boolean("Manually Processed",
                                        help="If This field is True then it will be hidden from mismatch details",
                                        default=False)
    create_date = fields.Datetime("Created Date")
    user_id = fields.Many2one("res.users", string="Responsible")
    skip_record = fields.Boolean("Skip Line")
    shipstation_order_reference = fields.Char("Shipstation Ref")
