import datetime

from odoo import http
from odoo.tools import pycompat

from odoo.addons.web.controllers.main import ExcelExport, ExportXlsxWriter


class ExcelExportInherit(ExcelExport, http.Controller):
    def from_data(self, fields, rows):
        results = []
        try:
            index = fields.index('Forecasted quantity at date/Date')
            index_demand_forecast = fields.index('Forecasted quantity at date/Demand Forecast')

            for row_index, row in enumerate(rows):
                if not row[index_demand_forecast]:
                    row[index_demand_forecast] = 0
                if row[index] and row[index] < datetime.datetime.today().date():
                    for i in range(0, index):
                        rows[row_index + 1][i] = row[i]
                else:
                    results.append(row)
        except ValueError:
            pass

        rows = results and results or rows
        return super().from_data(fields, rows)
