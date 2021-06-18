import datetime

from odoo import http
from odoo.tools import pycompat

from odoo.addons.web.controllers.main import ExcelExport, ExportXlsxWriter


class ExcelExportInherit(ExcelExport, http.Controller):
    def from_data(self, fields, rows):
        with ExportXlsxWriter(fields, len(rows)) as xlsx_writer:
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
            for row_index, row in enumerate(rows):
                for cell_index, cell_value in enumerate(row):
                    if isinstance(cell_value, (list, tuple)):
                        cell_value = pycompat.to_text(cell_value)
                    xlsx_writer.write_cell(row_index + 1, cell_index, cell_value)

        return xlsx_writer.value
