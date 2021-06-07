# -*- coding: utf-8 -*-
import json
import base64
import lxml

from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.tools import append_content_to_html, config
from odoo.tools.misc import formatLang
from odoo.tools.translate import _


class FollowUpReportUSA(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_columns_name(self, options):
        """
        Override
        Return the name of the columns of the follow-ups report
        """
        headers = [{'name': _('Transaction Name'), 'style': 'text-align:left; white-space:nowrap;'},
                   {'name': _('Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Due Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Source Document'), 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Memo'), 'style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('Expected Date'), 'class': 'date', 'style': 'white-space:nowrap;'},
                   {'name': _('Excluded'), 'class': 'date', 'style': 'white-space:nowrap;'},
                   {'name': _('Open Amount'), 'class': 'number', 'style': 'text-align:right; white-space:nowrap;'}
                  ]
        if self.env.context.get('print_mode'):
            headers = headers[:5] + headers[7:]  # Remove the 'Expected Date' and 'Excluded' columns
        return headers

    def format_values_report(self, values, currency):
        for key in values:
            values[key][1] = formatLang(self.env, values[key][1], currency_obj=currency)
        return values

    @staticmethod
    def _rename_column(lines, old_column_name, new_column_name):
        for i, line in reversed(list(enumerate(lines))):
            for j, column in enumerate(line['columns']):
                if column.get('name', False) == old_column_name:
                    lines[i]['columns'][j]['name'] = new_column_name
                    return

    def _get_lines(self, options, line_id=None):
        lines = super(FollowUpReportUSA, self)._get_lines(options, line_id)
        self._rename_column(lines, 'Total Due', 'Total Open Amount')
        for line in lines:
            if line.get('level') == 0 and line.get('columns') == []:
                line['class'] = 'o_account_reports_level0_no_border'
        return lines

    def _get_summary_lines(self, options):
        partner = options.get('partner_id') and self.env['res.partner'].browse(options['partner_id']) or False
        if not partner:
            return []

        res = {}
        today = fields.Date.today()
        lines = []
        line_num = len(lines)

        for l in partner.unreconciled_aml_ids:
            if self.env.context.get('print_mode') and l.blocked:
                continue
            currency = l.currency_id or l.company_id.currency_id
            if currency not in res:
                res[currency] = []
            res[currency].append(l)

        for currency, aml_recs in res.items():
            values = {
                'not_due':  [_('Not Due'),                  0],
                '1_30':     [_('1 - 30 Days Past Due'),     0],
                '31_60':    [_('31 - 60 Days Past Due'),    0],
                '61_90':    [_('61 - 90 Days Past Due'),    0],
                '91_120':   [_('91 - 120 Days Past Due'),   0],
                '120+':     [_('120+ Days Past Due'),       0],
                'total':    [_('Total Amount'),             0]
            }

            for aml in filter(lambda r: not r.blocked, aml_recs):
                amount = aml.currency_id and aml.amount_residual_currency or aml.amount_residual
                date_maturity = aml.date_maturity or aml.date or today
                number_due_days = (fields.Date.today() - date_maturity).days

                values['total'][1] += amount
                if number_due_days < 1:
                    values['not_due'][1] += amount
                elif 0 < number_due_days < 31:
                    values['1_30'][1] += amount
                elif 30 < number_due_days < 61:
                    values['31_60'][1] += amount
                elif 60 < number_due_days < 91:
                    values['61_90'][1] += amount
                elif 90 < number_due_days < 121:
                    values['91_120'][1] += amount
                elif number_due_days > 120:
                    values['120+'][1] += amount

            values = self.format_values_report(values, currency)
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': 'summary_title',
                'unfoldable': False,
                'level': 0,
                'columns': [values[key][0] for key in values]
            })
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': 'summary_values',
                'unfoldable': False,
                'level': 0,
                'columns': [values[key][1] for key in values]
            })
        return lines

    def get_html(self, options, line_id=None, additional_context=None):
        if additional_context is None:
            additional_context = {}
        additional_context['summary_lines'] = self._get_summary_lines(options)
        return super(FollowUpReportUSA, self).get_html(options, line_id=line_id, additional_context=additional_context)

    def create_attachment(self, options, financial_id=None):
        report_obj = self.sudo()
        if financial_id:
            report_obj = report_obj.browse(int(financial_id))
        report_name = report_obj.get_report_filename(options)
        pdf_binary = report_obj.get_pdf(options)
        name = '%s - %s.pdf' % (report_name, str(fields.Date.today()))
        attachment = self.env['ir.attachment'].sudo().create({
            'name': name,
            'datas': base64.encodebytes(pdf_binary),
            'type': 'binary'})
        return attachment

    # not call super
    @api.model
    def send_email(self, options):
        """
        Send by mail the followup to the customer
        """
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        email = self.env['res.partner'].browse(partner.address_get(['invoice'])['invoice']).email
        options['keep_summary'] = True
        if email and email.strip():
            # When printing we need te replace the \n of the summary by <br /> tags
            body_html = self.with_context(print_mode=True, mail=True, lang=partner.lang or self.env.user.lang).get_html(options)
            start_index = body_html.find(b'<span>', body_html.find(b'<div class="o_account_reports_summary">'))
            end_index = start_index > -1 and body_html.find(b'</span>', start_index) or -1
            if end_index > -1:
                replaced_msg = body_html[start_index:end_index].replace(b'\n', b'<br />')
                body_html = body_html[:start_index] + replaced_msg + body_html[end_index:]
            msg = _('Follow-up email sent to %s') % email
            msg += '<br>' + body_html.decode('utf-8')
            msg_id = partner.message_post(body=msg)

            # add pdf report as attachment
            report_attachment = self.create_attachment(options)

            email = self.env['mail.mail'].with_context(default_mail_message_id=msg_id).create({
                'mail_message_id': msg_id.id,
                'subject': '%s - Balance statement - %s' % (self.env.company.name, partner.name),
                'body_html': append_content_to_html(body_html, self.env.user.signature or '', plaintext=False),
                'email_from': self.env.user.email or '',
                'email_to': email,
                'body': msg,
                'attachment_ids': [(4, report_attachment.id)],
            })
            partner.message_subscribe([partner.id])

            return True
        raise UserError(_('Could not send mail to partner because it does not have any email address defined'))

    @api.model
    def print_followups(self, records):
        """
        Override to fix bug when print multiple records, may not need when Odoo fixes it
        """
        res_ids = records['ids'] if 'ids' in records else records.ids  # records come from either JS or server.action
        for res_id in res_ids:
            self.env['res.partner'].browse(res_id).message_post(body=_('Follow-up letter printed'))
        return self.env.ref('account_followup.action_report_followup').report_action(res_ids)
