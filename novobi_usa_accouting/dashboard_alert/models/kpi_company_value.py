# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


import logging

from ..utils.utils import is_equal
from odoo import api, models, fields, modules, tools, _
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class KPICompanyValue(models.Model):
    _name = "kpi.company.value"
    _description = "Model save value of all KPIs of each company"

    value = fields.Float()
    value_pre_period = fields.Float()
    last_update_value = fields.Datetime(string='Last Update Value',
                                        default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', 'Company')
    kpi_id = fields.Many2one('kpi.journal')

    @api.model
    def create(self, values):
        """ Create a sequence, in implementation == standard a fast gaps-allowed PostgreSQL sequence is used.
        """
        seq = super(KPICompanyValue, self).create(values)
        self.update_alert_info(seq.kpi_id.id, seq.company_id.id, seq.value)
        return seq

    def unlink(self):
        # TO DO
        return super(KPICompanyValue, self).unlink()

    def write(self, values):
        res = super(KPICompanyValue, self).write(values)
        for kpi_com_val in self:
            kpi_id = kpi_com_val.kpi_id.id
            company_id = kpi_com_val.company_id.id
            kpi_value = values['value']

            self.update_alert_info(kpi_id, company_id, kpi_value)

        return res

    ########################################################
    # GENERAL FUNCTION
    ########################################################
    def update_alert_info(self, kpi_id, company_id, value):
        modelAI = self.env['alert.info']
        alerts = modelAI.search([
            ('kpi_id', '=', kpi_id),
            ('company_id', '=', company_id)])
        for alert in alerts:
            write_data = {}

            _logger.info("Update alert info for KPI %s with value %s (previous value is %s) "
                         "in the %s times" %
                         (alert.kpi_id.name, value, alert.previous_value, alert.times_reach_to_condition,))
            code = "reached_condition = " + str(value) + alert.condition + str(alert.value)
            context = {}
            safe_eval(code, context, mode="exec", nocopy=True)
            reached_condition = context.get('reached_condition')
            previous_status = safe_eval(str(alert.previous_value) + alert.condition + str(alert.value))

            if not is_equal(value, alert.previous_value):
                times_reach_to_condition = alert.times_reach_to_condition
                if reached_condition and not previous_status:
                    times_reach_to_condition += 1
                    write_data.update({'times_reach_to_condition': times_reach_to_condition})

                write_data.update({
                    'previous_value': value,
                })

            if reached_condition:
                write_data["nearest_right"] = fields.datetime.now()
            else:
                write_data["nearest_right"] = None
            alert.write(write_data)
