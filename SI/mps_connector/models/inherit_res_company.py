# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    ###############################
    # EXTEND FUNCTION
    ###############################
    def write(self, values):
        """
            Extend the write function of ResCompany to handle the event that the user
            changes the MPS manufacturing_period(Time Range)
        :param dict values:
        :return:
        :rtype:
        """
        res = super(ResCompany, self).write(values)
        if 'manufacturing_period' in values:
            # If the user change the manufacturing_period and it different from company' manufacturing_period
            mps_env = self.env['mrp.production.schedule'].sudo()
            demand_fore_data_dict = mps_env.get_demand_fore_data_dict(company_id=self.id)

            # 1. Generate the product forecast configuration for concerning product
            mps_env.generate_product_forecast_configuration(demand_fore_data_dict=demand_fore_data_dict)

            # 2. Generate the forecast result for concerning product
            mps_env.generate_forecast_result(demand_fore_data_dict=demand_fore_data_dict)

            # 3. Summarize the historical data for concerning product
            mps_env.generate_summarized_historical_demand(demand_fore_data_dict=demand_fore_data_dict)

        return res
