# -*- coding: utf-8 -*-

import logging

from odoo.addons.si_core.utils.string_utils import PeriodType

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ForecastItem(models.Model):
    _inherit = 'forecast.item'

    @api.multi
    def create_material_forecast_items(self, tuple_keys, company_id):
        """ The function support create forecast items push on tuple of keys
        and set will forecast for it is False by default

        :param int company_id:
        :param list[tuple] tuple_keys:
        Ex: [(product_id, company_id, warehouse_id))]
        :return:
        """
        company_fis = self.search([('company_id', '=', company_id)])

        company = self.env['res.company'].browse(company_id)

        forecast_level_id = company.forecast_level_id
        product_field = forecast_level_id.get_product_field()

        exist_keys = [(getattr(fi, product_field).id,
                       fi.company_id and fi.company_id.id or False,
                       fi.warehouse_id and fi.warehouse_id.id or False)
                      for fi in company_fis]
        missing_keys = list(set(tuple_keys) - set(exist_keys))
        create_data = []
        for k in missing_keys:
            create_data.append({
                product_field: k[0],
                'company_id': k[1],
                'warehouse_id': k[2],
                'will_forecast': False,
                'sequence': 10000,
                'period_type': PeriodType.DEFAULT_PERIOD_TYPE
            })

        self.create(create_data)
