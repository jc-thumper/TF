from odoo import models, api, _
from odoo.addons.web.controllers.main import clean_action
import ast


class report_vendor_1099(models.AbstractModel):
    _name = "vendor.1099.report"
    _description = "Vendor 1099 Report"
    _inherit = 'account.report'
    
    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_year'}
    
    def _get_columns_name(self, options):
        return [{'name': 'Name'},
                {'name': 'EIN/SSN Number'},
                {'name': 'Address'},
                {'name': 'Amount Paid', 'class': 'number'}]
    
    def _get_templates(self):
        templates = super(report_vendor_1099, self)._get_templates()
        templates['main_template'] = 'l10n_us_accounting.template_usa_1099_report'
        return templates
    
    def _get_report_name(self):
        return _('Vendor 1099 Report')
    
    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        partners = self._get_result_lines(options)
        
        total_amount = 0
        for p in partners:
            vals = {
                'id': p['partner_odoo_id'],
                'name': p['partner_name'],
                'level': 2,
                'caret_options': 'vendor.1099',
                'columns': [{'name': v} for v in [p['partner_ssn'],
                                                  p['partner_address'],
                                                  self.format_value(p['total_balance'])]],
            }
            lines.append(vals)
            total_amount += p['total_balance']
        
        total_line = {
            'id': 'total.amount.1099',
            'name': _('Total'),
            'level': 2,
            'class': 'total',
            'columns': [{'name': ''}, {'name': ''}, {'name': self.format_value(total_amount), 'class': 'number'}],
        }
        lines.append(total_line)
        return lines
    
    def _get_result_lines(self, options):
        cr = self.env.cr
        query_move_line = self._get_move_lines_query_statement(options, {'eligible_filter': True})
        query = """
            SELECT *
            FROM (
                SELECT partner_odoo_id, partner_name, partner_ssn, partner_address,
                        SUM((debit - credit) * matched_percentage)  as total_balance
                FROM ({}) as result_table
                GROUP BY partner_odoo_id, partner_ssn, partner_address, partner_name
                ORDER BY UPPER(partner_name)
            ) as final_result
            WHERE total_balance != 0;
        """.format(query_move_line)
        
        cr.execute(query)
        
        partners = cr.dictfetchall()
        return partners
    
    def _get_move_lines_query_statement(self, options, params={}):
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        company_ids = self.env.context.get('company_ids', (self.env.user.company_id.id,))
        # Exclude payment method of Credit Card type(inbound and outbound) from 1099 tax report
        untrack_payment_methods = (self.env.ref('payment.account_payment_method_electronic_in').id,
                                   self.env.ref('l10n_us_accounting.account_payment_method_electronic_out').id)
        partner_filter = ''
        eligible_filter = ''
        payment_eligible_filter = ''
        if params:
            if params.get('id'):
                partner_filter = """AND aml.partner_id = {}""".format(params['id'])
            if params.get('eligible_filter'):
                eligible_filter = """AND aml.eligible_for_1099 = True"""
                payment_eligible_filter = "AND aml3.eligible_for_1099 = True"
        query_stmt = """
                        SELECT move_line.payment_move_line_id as line_id,
                           aml.partner_id as partner_odoo_id,
                           partner.name as partner_name,
                           partner.vat as partner_ssn,
                           CONCAT(partner.street, ' ', partner.street2, ' ', partner.city, ' ',
                                        res_country_state.code, ' ', partner.zip) as partner_address,
                           aml.debit, aml.credit,
                           (move_line.reconciled_amount / am.amount_total) as matched_percentage
                                      
                        FROM (
                           SELECT move_line.move_line_id, move_line.payment_move_line_id, SUM(amount) as reconciled_amount, move_line.eligible_for_1099
                           FROM (
                                 SELECT apr.credit_move_id as move_line_id, apr.amount as amount, aml3.id as payment_move_line_id, aml3.eligible_for_1099 as eligible_for_1099
                                 FROM account_partial_reconcile apr
                                      join account_move_line aml3 on apr.debit_move_id = aml3.id
                                      join account_move_line aml4 on aml3.move_id = aml4.move_id
                                      join account_account as aa3 on aml4.account_id = aa3.id
                                      join account_move as am2 on aml4.move_id = am2.id
                                      join account_account_type as aat on aa3.user_type_id = aat.id
                                      left join account_payment as ap on aml4.payment_id = ap.id
                                      left join account_payment_method as apm on ap.payment_method_id = apm.id
                                 WHERE am2.state = 'posted'
                                      AND aat.type = 'liquidity' AND aat.internal_group = 'asset'
                                      AND (apm.id NOT IN {untrack_payment_methods} OR apm.id IS NULL)
                                      {payment_eligible_filter}

                                 UNION
                                 SELECT apr.debit_move_id as move_line_id, apr.amount as amount, aml3.id as payment_move_line_id, aml3.eligible_for_1099 as eligible_for_1099
                                 FROM account_partial_reconcile apr
                                      join account_move_line aml3 on apr.credit_move_id = aml3.id
                                      join account_move_line aml4 on aml3.move_id = aml4.move_id
                                      join account_account as aa3 on aml4.account_id = aa3.id
                                      join account_move as am2 on aml4.move_id = am2.id
                                      join account_account_type as aat on aa3.user_type_id = aat.id
                                      left join account_payment as ap on aml4.payment_id = ap.id
                                      left join account_payment_method as apm on ap.payment_method_id = apm.id
                                 WHERE am2.state = 'posted'
                                      AND aat.type = 'liquidity' AND aat.internal_group = 'asset'
                                      AND (apm.id NOT IN {untrack_payment_methods} OR apm.id IS NULL)
                                      {payment_eligible_filter}
                                      
                                 UNION
                                 SELECT aml4.id as move_line_id, am2.amount_total as amount, aml4.id as payment_move_line_id, aml4.eligible_for_1099 as eligible_for_1099
                                 FROM account_move_line aml3
                                      join account_move as am2 on aml3.move_id = am2.id
                                      join account_move_line aml4 on am2.id = aml4.move_id
                                      join account_account as aa3 on aml3.account_id = aa3.id
                                      join account_account as aa4 on aml4.account_id = aa4.id
                                      join account_account_type as aat on aa3.user_type_id = aat.id
                                      left join account_payment as ap on aml3.payment_id = ap.id
                                      left join account_payment_method as apm on ap.payment_method_id = apm.id
                                 WHERE am2.state = 'posted'
                                      AND aat.type = 'liquidity' AND aat.internal_group = 'asset'
                                      AND (apm.id NOT IN {untrack_payment_methods} OR apm.id IS NULL)
                                      AND aml3.id != aml4.id
                                      AND aa4.account_eligible_1099 = True
                                      AND aa4.reconcile = False
                           ) as move_line
                           GROUP BY move_line.move_line_id, move_line.payment_move_line_id, move_line.eligible_for_1099
                        ) as move_line
                             join account_move_line aml2 on aml2.id = move_line.move_line_id
                             join account_move as am ON aml2.move_id = am.id
                             join account_move_line AS aml on aml2.move_id = aml.move_id
                             join res_partner as partner on aml.partner_id = partner.id
                             join account_account as aa on aml.account_id = aa.id
                             left join res_country_state on partner.state_id = res_country_state.id
                                      
                        WHERE am.state = 'posted'
                             AND aa.account_eligible_1099 = True
                             AND aa.reconcile = False
                             AND aml.date >= '{date_from}' AND aml.date <= '{date_to}'
                             AND partner.vendor_eligible_1099 = True
                             AND aml.company_id IN ({company_ids})
                             {partner_filter}
                             {eligible_filter}
                        """.format(untrack_payment_methods=untrack_payment_methods,
                                   date_from=date_from, date_to=date_to,
                                   company_ids=','.join(str(company) for company in company_ids),
                                   partner_filter=partner_filter, eligible_filter=eligible_filter,
                                   payment_eligible_filter=payment_eligible_filter)
        return query_stmt
    
    def open_vendor_1099(self, options, params):
        action = self.env.ref('l10n_us_accounting.action_see_detailed_move_lines').read()[0]
        action = clean_action(action)
        
        if params and params.get('id') and options:
            cr = self.env.cr
            query_stmt = self._get_move_lines_query_statement(options, params)
            cr.execute(query_stmt)
            lines = cr.dictfetchall()
            line_ids = [line['line_id'] for line in lines]
            action['domain'] = [('id', 'in', line_ids)]
        
        return action
    
    @api.model
    def open_all_vendor_transactions(self, options):
        if not options:
            return None
        cr = self.env.cr
        options = ast.literal_eval(options)
        query_stmt = self._get_move_lines_query_statement(options)
        cr.execute(query_stmt)
        lines = cr.dictfetchall()
        line_ids = [line['line_id'] for line in lines]
        list_view = self.env.ref('l10n_us_accounting.view_move_line_tree_1099')
        search_view = self.env.ref('l10n_us_accounting.view_eligible_1099_search')
        return {
            'name': _('All Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,pivot,graph,form,kanban',
            'view_type': 'list',
            'views': [[list_view.id, 'list'], [False, 'pivot'], [False, 'graph'], [False, 'form'],
                      [False, 'kanban']],
            'search_view_id': [search_view.id, 'search'],
            'domain': [('id', 'in', line_ids)],
            'context': {'search_default_filter_eligible_1099_lines': 1},
            'target': 'current',
        }
