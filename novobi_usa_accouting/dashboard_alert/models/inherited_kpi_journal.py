# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, models, fields, modules, tools, _


class InheritedKPIJournal(models.Model):
    _inherit = 'kpi.journal'

    kpi_comp_ids = fields.One2many('kpi.company.value', 'kpi_id')

    ########################################################
    # KPI GENERATOR
    ########################################################
    def get_data_kpi_render(self, info, dict_context, dict_lines_data):
        """ Function support return the dictionary is the data to render a kpi item
        that contain the data in 'info' variable

        :param dict_lines_data:
        :param dict_context:
        :param info:
        :return:
        """

        res = super(InheritedKPIJournal, self)\
            .get_data_kpi_render(info, dict_context, dict_lines_data)

        kpi_info_detail = info.kpi_id
        res.update({
            'kpi_id': kpi_info_detail.id
        })
        return res

    ########################################################
    # CRON JOB
    ########################################################
    @api.model
    def _automated_compute_kpi_value(self):
        print('_automated_compute_kpi_value')
        companies = self.env['res.company'].search([], order='id')
        kpis = self.search([])

        modelKPICV = self.env['kpi.company.value']
        kpi_company_value_dict = dict(modelKPICV.search([])
                                      .mapped(lambda item: ((item.company_id.id, item.kpi_id.id), item)))

        for company in companies:

            pre_period_kpi_value_dict = self.env['kpi.journal']\
                .get_json_kpi_info(kpis.ids, delta_periods=-1, lines_dict={})

            cur_period_kpi_value_dict = self.env['kpi.journal'] \
                .get_json_kpi_info(kpis.ids, delta_periods=0, lines_dict={})

            for kpi in kpis:
                value = cur_period_kpi_value_dict[kpi.code_name]['value']
                value_pre_period = pre_period_kpi_value_dict[kpi.code_name]['value']
                kpi_company_value = kpi_company_value_dict.get((company.id, kpi.id))
                if kpi_company_value:
                    kpi_company_value.write({
                        'value': value,
                        'value_pre_period': value_pre_period,
                        'last_update_value': fields.Datetime.now()
                    })
                else:
                    modelKPICV.create({
                        'value': value,
                        'value_pre_period': value_pre_period,
                        'company_id': company.id,
                        'kpi_id': kpi.id
                    })
