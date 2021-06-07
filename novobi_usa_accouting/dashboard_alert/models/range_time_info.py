# Copyright 2020 Novobi
# See LICENSE file for full copyright and licensing details.


from odoo import api, models, fields, modules, tools, _

ALL_DATE = 0
MON = 1
TUE = 2
WEN = 3
THU = 4
FIR = 5
SAT = 6
SUN = 7


class RangeTimeInfo(models.Model):
    _name = "range.time.info"
    _description = "Range time information"

    date_in_week_list = [(ALL_DATE, _('All Dates')),
                         (MON, _('Monday')),
                         (TUE, _('Tuesday')),
                         (WEN, _('Wednesday')),
                         (THU, _('Thursday')),
                         (FIR, _('Friday')),
                         (SAT, _('Saturday')),
                         (SUN, _('Sunday')),]

    start = fields.Float('Start Time', default=0)
    end = fields.Float('End Time', default=23.98)
    date_in_week = fields.Float(selection=date_in_week_list, default=ALL_DATE)
