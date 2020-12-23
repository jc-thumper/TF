import logging

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger("Teqstars:Base Marketplace")


class MkQueueJob(models.Model):
    _name = "mk.queue.job"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Marketplace Queue Job'
    _order = "id desc"

    @api.depends('mk_queue_line_ids.state')
    def _compute_queue_line_counts_and_state(self):
        for queue in self:
            mk_queue_line_ids = queue.mk_queue_line_ids
            queue.total_count = len(mk_queue_line_ids)
            queue.draft_count = len(mk_queue_line_ids.filtered(lambda x: x.state == 'draft'))
            queue.processed_count = len(mk_queue_line_ids.filtered(lambda x: x.state == 'processed'))
            queue.cancelled_count = len(mk_queue_line_ids.filtered(lambda x: x.state == 'cancelled'))
            queue.failed_count = len(mk_queue_line_ids.filtered(lambda x: x.state == 'failed'))
            if all(line.state == 'processed' or line.state == 'cancelled' for line in mk_queue_line_ids):
                queue.state = 'processed'
            elif all(line.state == 'draft' for line in mk_queue_line_ids):
                queue.state = 'draft'
            elif all(line.state == 'failed' for line in mk_queue_line_ids):
                queue.state = 'failed'
            else:
                queue.state = 'partial_processed'

    name = fields.Char('Name', readonly=True, required=True, default=lambda self: _('New'))
    mk_instance_id = fields.Many2one('mk.instance', "Instance", ondelete='cascade', required=True)
    type = fields.Selection([('customer', 'Customer Import'), ('product', 'Product Import'), ('order', 'Order Import')], required=True)
    state = fields.Selection([('draft', 'Draft'), ('partial_processed', 'Partial Processed'), ('processed', 'Processed'), ('failed', 'Failed')],
                             default='draft', compute="_compute_queue_line_counts_and_state", store=True, track_visibility='onchange')
    mk_queue_line_ids = fields.One2many("mk.queue.job.line", "queue_id", string="Queue Lines", copy=False)
    mk_log_id = fields.Many2one('mk.log', string="Logs")
    total_count = fields.Integer(string='Total Count', compute='_compute_queue_line_counts_and_state', compute_sudo=True)
    draft_count = fields.Integer(string='Draft Count', compute='_compute_queue_line_counts_and_state', compute_sudo=True)
    processed_count = fields.Integer(string='Processed Count', compute='_compute_queue_line_counts_and_state', compute_sudo=True)
    cancelled_count = fields.Integer(string='Cancelled Count', compute='_compute_queue_line_counts_and_state', compute_sudo=True)
    failed_count = fields.Integer(string='Fail Count', compute='_compute_queue_line_counts_and_state', compute_sudo=True)
    no_of_retry_count = fields.Integer(string="Retry Count", help="No of count that queue went in process.", compute_sudo=True)

    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('mk.queue.job') or _('New')
        res = super(MkQueueJob, self).create(vals)
        return res

    def action_create_queue_lines(self, line_vals):
        self.ensure_one()
        queue_job_line_obj = self.env['mk.queue.job.line']
        # Searching for existing line where created to import same before this request and updating the state to cancelled.
        existing_lines = self.env['mk.queue.job.line'].search([('mk_id', '=', line_vals.get('mk_id')), ('state', 'in', ['draft', 'failed']), ('queue_id.type', '=', self.type)])
        if existing_lines:
            existing_lines.write({'state': 'cancelled'})
        if not line_vals:
            return self.env['mk.queue.job.line']
        line_vals.update({'queue_id': self.id})
        return queue_job_line_obj.create(line_vals)

    def action_view_queue_lines(self):
        action = self.env.ref('base_marketplace.action_queue_job_line_all').read()[0]
        context = {}
        if self.env.context.get('show_draft', False):
            context.update({'search_default_draft': 1})
        elif self.env.context.get('show_processed', False):
            context.update({'search_default_processed': 1})
        elif self.env.context.get('show_failed', False):
            context.update({'search_default_failed': 1})
        elif self.env.context.get('show_cancelled', False):
            context.update({'search_default_cancelled': 1})
        action['context'] = context
        return action

    def action_click_on_retry_count(self):
        return True

    def do_process(self, cron=False):
        self.ensure_one()
        if not self.mk_log_id:
            mk_log_id = self.env['mk.log'].create_update_log(mk_instance_id=self.mk_instance_id, operation_type='import')
            self.mk_log_id = mk_log_id.id
        else:
            mk_log_id = self.mk_log_id
        mk_log_line_dict = self.env.context.get('mk_log_line_dict', {'error': [], 'success': []})
        if hasattr(self, '%s_%s_queue_process' % (self.mk_instance_id.marketplace, self.type)):
            getattr(self.with_context({'mk_log_line_dict': mk_log_line_dict, 'hide_notification': not cron}),
                    '%s_%s_queue_process' % (self.mk_instance_id.marketplace, self.type))()
        if not mk_log_id.log_line_ids:
            mk_log_id.unlink()
        return True

    def cron_do_process(self):
        for record in self.search(
                [('state', 'not in', ['failed', 'processed']), '|', ('no_of_retry_count', '<', 3), ('no_of_retry_count', '=', False), ('mk_instance_id.state', '=', 'confirmed')],
                order='id'):
            try:
                record.do_process(cron=True)
            except Exception as e:
                record.message_post(body='Facing issue while process Queue {}, ERROR: {}'.format(record.name, e))
            finally:
                if record.no_of_retry_count == 2 and record.failed_count:
                    record.create_activity_action(
                        "System tried 3 times to process queue but something went wrong! Therefor, Manual attention needed to process failed queue lines.")
                record.no_of_retry_count += 1
            self.env.cr.commit()  # TODO: Need to check working.
        return True

    def action_mark_as_complete(self):
        queue_line_ids = self.mk_queue_line_ids.filtered(lambda x: x.state in ['draft', 'failed'])
        for line in queue_line_ids:
            line.write({'state': 'cancelled'})
        self.message_post(body=_("Queue lines were manually set to cancelled : %s") % (', '.join(queue_line_ids.mapped('mk_id'))))
        return True

    def create_activity_action(self, activity_note):
        mail_activity_obj = self.env['mail.activity']
        mk_instance_id, model_id, date_deadline = self.mk_instance_id, False, False
        activity_date_deadline_range_type = mk_instance_id.activity_date_deadline_range_type
        activity_date_deadline_range = mk_instance_id.activity_date_deadline_range
        activity_type_id = mk_instance_id.mk_activity_type_id
        model_id = self.env['ir.model'].search([('model', '=', 'mk.queue.job')]).id
        if activity_type_id and activity_date_deadline_range_type and activity_date_deadline_range:
            date_deadline = fields.Date.context_today(mk_instance_id) + relativedelta(**{activity_date_deadline_range_type: activity_date_deadline_range})
            for user_id in mk_instance_id.activity_user_ids:
                vals = {'activity_type_id': activity_type_id.id,
                        'note': activity_note,
                        'res_id': self.id,
                        'user_id': user_id.id,
                        'res_model_id': model_id,
                        'date_deadline': date_deadline}
                try:
                    mail_activity_obj.create(vals)
                except Exception as e:
                    _logger.error("Error while creating activity, ERROR: {}".format(e))

    def do_retry_failed(self):
        if not self.mk_log_id:
            mk_log_id = self.env['mk.log'].create_update_log(mk_instance_id=self.mk_instance_id, operation_type='import')
            self.mk_log_id = mk_log_id.id
        else:
            mk_log_id = self.mk_log_id
        if hasattr(self, '%s_%s_retry_failed_queue' % (self.mk_instance_id.marketplace, self.type)):
            getattr(self.with_context(mk_log_id=mk_log_id), '%s_%s_retry_failed_queue' % (self.mk_instance_id.marketplace, self.type))()
        return True


class MkQueueJobLine(models.Model):
    _name = "mk.queue.job.line"
    _description = 'Queue Line'

    name = fields.Char(string="Name", required=True)
    mk_id = fields.Char("Marketplace ID", copy=False)
    state = fields.Selection([('draft', 'Draft'), ('processed', 'Processed'), ("cancelled", "Cancelled"), ('failed', 'Failed')], default='draft')
    queue_id = fields.Many2one("mk.queue.job", string="Queue", ondelete='cascade', required=True)
    log_line_ids = fields.One2many("mk.log.line", "queue_job_line_id", string="Log Lines")
    mk_instance_id = fields.Many2one('mk.instance', string='Instance', related='queue_id.mk_instance_id', store=False)
    processed_date = fields.Datetime("Processed At", readonly=True)
    data_to_process = fields.Text("Data", copy=False)

    def do_retry_failed(self):
        if not self.queue_id.mk_log_id:
            mk_log_id = self.env['mk.log'].create_update_log(mk_instance_id=self.mk_instance_id, operation_type='import')
            self.queue_id.mk_log_id = mk_log_id.id
        else:
            mk_log_id = self.queue_id.mk_log_id
        if hasattr(self, '%s_%s_retry_failed_queue' % (self.queue_id.mk_instance_id.marketplace, self.queue_id.type)):
            getattr(self.with_context(mk_log_id=mk_log_id), '%s_%s_retry_failed_queue' % (self.queue_id.mk_instance_id.marketplace, self.queue_id.type))()
        return True
