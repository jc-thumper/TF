from odoo import fields, models, api, _


class BillableExpenseReport(models.AbstractModel):
    _inherit = 'account.report'
    _name = 'billable.expense.report'
    _description = 'Pending Billable Expense'

    filter_date = {'filter': 'today'}

    def _get_templates(self):
        templates = super(BillableExpenseReport, self)._get_templates()
        templates['line_template'] = 'account_billable_expense.line_template_billable_expense_report'
        templates['main_template'] = 'account_billable_expense.template_billable_expense_report'
        templates['search_template'] = 'account_billable_expense.search_template_expense'
        return templates

    def _get_columns_name(self, options):
        return [
            {},
            {'name': _('Date')},
            {'name': _('Source')},
            {'name': _('Supplier')},
            {'name': _('Description')},
            {'name': _('Amount'), 'class': 'number'},
            {'name': _('On Draft Invoice')},
        ]

    def group_by_partner_id(self, options, line_id):
        domain = [('billable_expenses_ids', '!=', False)]
        if line_id:
            domain.append(('id', '=', line_id))

        customer_ids = self.env['res.partner'].search(domain)
        company_ids = self.env.companies.ids

        partners = {}
        for partner in customer_ids:
            outstanding_expenses = partner.get_outstanding_expenses(options, company_ids)
            if not outstanding_expenses:
                continue

            for l in outstanding_expenses:
                currency = l.currency_id
                if currency not in partners:
                    partners[currency] = {}
                if partner not in partners[currency]:
                    partners[currency][partner] = {}
                    partners[currency][partner]['lines'] = []

                amount = partners[currency][partner].get('amount', 0)
                partners[currency][partner]['amount'] = amount + l.amount_total
                partners[currency][partner]['lines'].append(l)

        return partners

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        unfold_all = True  # unfold by default

        if line_id:
            line_id = line_id.replace('partner_', '')

        partners = self.group_by_partner_id(options, line_id)

        for currency in partners:
            total_amount = 0
            sorted_partners = sorted(partners[currency], key=lambda p: p.name or '')

            for partner in sorted_partners:
                amount = partners[currency][partner]['amount']
                total_amount += amount

                partner_str = 'partner_' + str(partner.id)
                lines.append({
                    'id': partner_str,
                    'name': partner.name,
                    # [self.format_value(amount, currency=currency), '']:
                    #   use the empty string '' to add the empty column 'On Draft Invoice'
                    'columns': [{'name': v} for v in [self.format_value(amount, currency=currency), '']],
                    'unfoldable': True,
                    'unfolded': partner_str in options.get('unfolded_lines') or unfold_all,
                    'level': 2,
                    'colspan': 5,
                })

                if partner_str in options.get('unfolded_lines') or unfold_all:
                    domain_lines = []
                    for line in partners[currency][partner]['lines']:
                        on_draft_invoice = True if line.invoice_line_id else False

                        columns = [line.bill_date, 'Payable Invoice',
                                   line.supplier_id.name,
                                   line.description,
                                   self.format_value(line.amount_total, currency=currency),
                                   {'name': on_draft_invoice, 'blocked': on_draft_invoice}]
                        domain_lines.append({
                            'id': line.id,
                            'parent_id': partner_str,
                            'name': line.source_document,
                            'class': 'o_account_reports_level3 no-margin',
                            'columns': [type(v) == dict and v or {'name': v} for v in columns],
                            'level': 3,
                            'caret_options': 'billable.expenses' if line.bill_id else 'purchase.expenses',
                        })
                    lines += domain_lines

            if not line_id:
                lines.append({
                    'id': 'grouped_partners_total',
                    'name': _('Total'),
                    'level': 0,
                    'class': '',
                    'columns': [{'name': v} for v in
                                ['', '', '', '', self.format_value(total_amount, currency=currency), '']],
                })

            # Add an empty line after the total to make a space between two currencies
            lines.append({
                'id': '',
                'name': '',
                'class': 'border-0',
                'unfoldable': False,
                'level': 0,
                'columns': [],
            })

        return lines

    @api.model
    def _get_report_name(self):
        return _('Pending Billable Expense')

    def open_bill_expense(self, options, params=None):
        if not params:
            params = {}
        ctx = self.env.context.copy()
        ctx.pop('id', '')
        expense_id = params.get('id')
        document = params.get('object', 'account.move')
        if expense_id:
            expense = self.env['billable.expenses'].browse(expense_id)
            bill_id = expense.bill_id.id
            view_id = self.env['ir.model.data'].get_object_reference('account', 'view_move_form')[1]
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'tree',
                'view_mode': 'form',
                'views': [(view_id, 'form')],
                'res_model': document,
                'view_id': view_id,
                'res_id': bill_id,
                'context': ctx,
            }
