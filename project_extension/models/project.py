from odoo import models, fields, api, _


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'
    stage_status = fields.Selection([
        ('open', 'Open'),
        ('completed', 'Completed'),
    ], default='open',
        string='Stage Status', copy=True)


class Project(models.Model):
    _inherit = "project.project"

    open_tasks_count = fields.Integer(compute='_compute_open_task_count', string="Open Tasks Count")
    all_open_tasks_count = fields.Integer(compute='_compute_all_open_task_count', string="All Open Tasks Count")
    all_tasks_count = fields.Integer(compute='_compute_all_task_count', string="All Tasks Count")

    @api.depends('task_ids.stage_id')
    def _compute_open_task_count(self):
        for project in self:
            project.open_tasks_count = self.env['project.task'].search_count(
                [('stage_id.stage_status', '=', 'open'), ('project_id', '=', project.id)])

    @api.depends('task_ids.stage_id')
    def _compute_all_open_task_count(self):
        for project in self:
            project.all_open_tasks_count = self.env['project.task'].with_context(active_test=False).search_count(
                [('stage_id.stage_status', '=', 'open'), ('project_id', '=', project.id)])

    def _compute_all_task_count(self):
        task_data = self.env['project.task'].with_context(active_test=False).read_group(
            [('project_id', 'in', self.ids), '|', ('stage_id.fold', '=', False), ('stage_id', '=', False)],
            ['project_id'], ['project_id'])
        result = dict((data['project_id'][0], data['project_id_count']) for data in task_data)
        for project in self:
            project.all_tasks_count = result.get(project.id, 0)

    def unlink(self):
        for project in self.with_context(active_test=False):
            if project.tasks:
                try:
                    project.tasks.unlink()
                except:
                    project.tasks.write({'active': False})
        result = super(Project, self).unlink()
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        project = super(Project, self).copy(default)
        for follower in self.message_follower_ids:
            project.with_context(apply_mode="direct").message_subscribe(partner_ids=follower.partner_id.ids,
                                                                        subtype_ids=follower.subtype_ids.ids)
        return project


class Task(models.Model):
    _inherit = "project.task"

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        task = super(Task, self).copy(default)
        for follower in self.message_follower_ids:
            task.with_context(apply_mode="direct").message_subscribe(partner_ids=follower.partner_id.ids,
                                                                     subtype_ids=follower.subtype_ids.ids)
        return task
