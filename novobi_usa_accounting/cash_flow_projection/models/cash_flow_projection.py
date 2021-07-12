# -*- coding: utf-8 -*-
##############################################################################

#    Copyright (C) 2019 Novobi LLC (<http://novobi.com>)
#
##############################################################################

from odoo import api, fields, models, _
import datetime
from dateutil.relativedelta import relativedelta


class CashFlowProjection(models.TransientModel):
    _name = 'cash.flow.projection'
    _description = 'Cash Flow Projection'
    
    @api.model
    def get_cash_flow_period_number(self):
        return {
            'period_number': self.env.company.cash_flow_period_number,
            'period_type': self.env.company.cash_flow_last_period_type,
        }
    
    @api.model
    def get_html(self, options={}):
        rcontext, num_period, period_unit = self.get_data(options)
        result = {
            'html': self.env.ref('cash_flow_projection.cash_flow_projection_report').render(rcontext),
            'report_context': {'nb_periods': num_period, 'period': period_unit},
        }
        return result
    
    @api.model
    def get_data(self, options={}):
        """
        Generate html elements for displaying in the cash flow projection table
        @param options: options for filtering records
        @return: a dictionary contains info for rendering cash flow projection table
        """
        periods = []
        num_period = options.get('num_period') or self.env.company.cash_flow_period_number or 6
        period_unit = options and options.get('period')
        if not options:
            period_unit = self.env.company.cash_flow_last_period_type
        date_spacing = week_spacing = month_spacing = 0
        if period_unit == 'day':
            date_spacing = 1
        elif period_unit == 'week':
            week_spacing = 1
        else:
            month_spacing = 1
        # Calculate the start day and end date of the cycle
        today = fields.Date.today()
        weekday = (today.weekday() + 1) % 7
        start_date = today - datetime.timedelta(weekday * week_spacing + (today.day - 1) * month_spacing)
        # Create list of date range
        date_list = []
        due_transaction_options = self.env['cash.flow.transaction.type'].sudo().search(
            [('code', '=', 'past_due_transaction')])
        if due_transaction_options and due_transaction_options.is_show and not options.get('from_chart', False):
            due_date = start_date - relativedelta(days=1)
            date_list.append({
                'start_date': due_date - relativedelta(months=1),
                'end_date': due_date,
                'period_order': -1,
                'is_due_period': True,
            })
        for i in range(0, num_period):
            # Calculate the start date and end date of each period
            period_start_date = start_date + relativedelta(months=month_spacing * i, weeks=week_spacing * i,
                                                           days=date_spacing * i)
            period_end_date = period_start_date + relativedelta(months=month_spacing,
                                                                weeks=week_spacing,
                                                                days=date_spacing) - relativedelta(days=1)
            # if i == 0:
            #     period_start_date = today
            date_list.append({
                'start_date': period_start_date,
                'end_date': period_end_date,
                'period_order': i,
                'is_due_period': False,
            })
        # Query accounts thar appear in the cash flow projection report
        transaction_list_in, transaction_list_out = self._get_default_lines(options)
        for date_period in date_list:
            i = date_period.get('period_order', 0)
            is_due_period = date_period.get('is_due_period', False)
            period_start_date = date_period.get('start_date', fields.Date.today())
            period_end_date = date_period.get('end_date', fields.Date.today())
            # Get period name
            period_name = self._get_period_name(period_start_date, period_end_date, period_unit, is_due_period)
            # Query cash in lines and render them in order to show in the report
            cash_in_lines = self.get_cash_in_lines(period_start_date, period_end_date, options)
            rendered_in_lines = []
            for transaction in transaction_list_in:
                amount = self._get_user_value(period_name, period_unit, 'cash_in', transaction['transaction_code'],
                                              is_due_period)
                rendered_in_lines.append({
                    'transaction_name': transaction['transaction_name'],
                    'transaction_code': transaction['transaction_code'],
                    'has_user_value': amount != 0,
                    'amount': amount,
                })
            for line in cash_in_lines:
                transaction = [account for account in transaction_list_in if
                               line['transaction_code'] == account['transaction_code']]
                if not len(transaction):
                    continue
                index = transaction_list_in.index(transaction[0])
                if not rendered_in_lines[index]['has_user_value']:
                    rendered_in_lines[index]['amount'] = line['amount']
            # Query cash out lines and render them in order to show in the report
            cash_out_lines = self.get_cash_out_lines(period_start_date, period_end_date, options)
            rendered_out_lines = []
            for transaction in transaction_list_out:
                amount = self._get_user_value(period_name, period_unit, 'cash_out', transaction['transaction_code'],
                                              is_due_period)
                rendered_out_lines.append({
                    'transaction_name': transaction['transaction_name'],
                    'transaction_code': transaction['transaction_code'],
                    'has_user_value': amount != 0,
                    'amount': amount,
                })
            for line in cash_out_lines:
                transaction = [account for account in transaction_list_out if
                               line['transaction_code'] == account['transaction_code']]
                if not len(transaction):
                    continue
                index = transaction_list_out.index(transaction[0])
                if not rendered_out_lines[index]['has_user_value']:
                    rendered_out_lines[index]['amount'] = line['amount']
            # Create the dictionary which contains the information of the period to show in the report
            opening_balance = i < 0 and 0 or round(
                i == 0 and self.get_opening_balance(today), 2) or 0.0
            period = {
                'period': period_name,
                'total_cash_in': round(sum(record['amount'] for record in rendered_in_lines), 2),
                'total_cash_out': round(sum(record['amount'] for record in rendered_out_lines), 2),
                'cash_in_lines': rendered_in_lines,
                'cash_out_lines': rendered_out_lines,
                'opening_balance': opening_balance,
                'forward_balance': i > 0 and periods[i - 1]['closing_balance'] or 0.0,
            }
            
            period['closing_balance'] = round(
                period['forward_balance'] + period['opening_balance'] + period['total_cash_in'] - period[
                    'total_cash_out'], 2)
            period['cash_flow'] = round(period['total_cash_in'] - period['total_cash_out'], 2)
            periods.append(period)
        # Render context
        rcontext = {
            'num_period': num_period,
            'periods': periods,
            'currency': self.env.company.currency_id,
            'period_type': period_unit,
        }
        return rcontext, num_period, period_unit

    def _get_companies(self):
        """
        Get selecting companies in string format '(1,2,3)'
        """
        companies = self.env.companies.ids
        companies_str = '{}'.format(tuple(companies))
        if len(companies) == 1:
            # If there is only one company selected, need to get rid of "," from the string "(1,)"
            companies_str = companies_str.replace(',', '')

        return companies_str
    
    def _get_period_name(self, start_date, end_date, period_type, is_due_period):
        """
        Get the name of the period
        @param start_date: the beginning date of the period
        @param end_date: the ending date of the period
        @return: the string name of the period
        """
        if is_due_period:
            return 'Past Due Transactions'
        if period_type == 'day':
            return start_date.strftime("%m/%d/%y")
        if period_type == 'week':
            return '{}-{}'.format(start_date.strftime("%m/%d/%y"), end_date.strftime("%m/%d/%y"))
        return start_date.strftime("%b %Y")
    
    def _get_default_lines(self, options):
        cash_in_default = []
        cash_out_default = []
        cash_in_configurations = options.get('cash_in') or []
        cash_out_configurations = options.get('cash_out') or []
        for configuration in cash_in_configurations:
            if configuration['is_show']:
                cash_in_default.append({
                    'transaction_name': configuration['name'],
                    'transaction_code': configuration['code'],
                    'amount': 0,
                })
        for configuration in cash_out_configurations:
            if configuration['is_show']:
                cash_out_default.append({
                    'transaction_name': configuration['name'],
                    'transaction_code': configuration['code'],
                    'amount': 0,
                })
        return cash_in_default, cash_out_default
    
    def _get_user_value(self, period, period_type, cash_type, transaction_code, is_due_period):
        """
        Get the old value for the period which was saved by users
        @param period: the string of period
        @param period_type: type of the period ('day', 'week', 'month')
        @param cash_type: cash_in or cash_out type
        @param transaction_code: code of the transaction ('incoming_payment', 'ar_invoice', ...)
        @return: the value which was saved before, or 0 if not existed
        """
        if is_due_period:
            return 0.0
        transaction_type = self.env['cash.flow.transaction.type'].sudo().search([('code', '=', transaction_code)])
        if not transaction_type:
            return 0.0
        custom_configuration = self.env['cash.flow.user.configuration'].sudo().search(
            [('cash_type', '=', cash_type), ('period_type', '=', period_type),
             ('transaction_type', '=', transaction_type.id),
             ('period', '=', period), ('company_id', 'in', self.env.companies.ids)])
        remaining_company_ids = (self.env.companies - custom_configuration.mapped('company_id'))
        default_configuration = self.env['cash.flow.user.configuration'].sudo().search(
                     [('cash_type', '=', cash_type), ('period_type', '=', period_type),
                      ('transaction_type', '=', transaction_type.id),
                      ('period', '=', period_type), ('company_id', 'in', remaining_company_ids.ids)])

        return sum((custom_configuration + default_configuration).mapped('value'))
    
    @api.model
    def save_user_value(self, options):
        """
        Save the value for the particular period which was typed by users
        @param options: the dictionary contains the value and options to save that value in the suitable period
        """
        if not options:
            return
        transaction_type = self.env['cash.flow.transaction.type'].sudo().search([('code', '=', options['code'])])
        if not transaction_type:
            return
        record = self.env['cash.flow.user.configuration'].sudo().search(
            [('cash_type', '=', options['cash_type']), ('period_type', '=', options['period_type']),
             ('transaction_type', '=', transaction_type.id),
             ('period', '=', options['period']), ('company_id', '=', self.env.company.id)])
        if not record:
            vals = {
                'period': options['period'],
                'period_type': options['period_type'],
                'cash_type': options['cash_type'],
                'transaction_type': transaction_type.id,
                'value': options['value'],
                'company_id': self.env.company.id,
            }
            self.env['cash.flow.user.configuration'].sudo().create(vals)
            return
        record.value = options['value']
    
    @api.model
    def save_last_period_option(self, period_type):
        if period_type in ['day', 'week', 'month']:
            self.env.company.cash_flow_last_period_type = period_type
        return
    
    @api.model
    def _get_currency_table(self, options):
        """ Construct the currency table as a mapping company -> rate to convert the amount to the user's company
        currency in a multi-company/multi-currency environment.
        The currency_table is a small postgresql table construct with VALUES.
        :param options: The report options.
        :return: The query representing the currency table.
        """
        main_company = self.env.company
        companies = self.env.companies
        currency_rates = companies.mapped('currency_id')._get_rates(main_company, fields.Date.today())
        
        conversion_rates = []
        for company in companies:
            conversion_rates.append((
                company.id,
                currency_rates[main_company.currency_id.id] / currency_rates[company.currency_id.id],
                main_company.currency_id.decimal_places,
            ))
        
        currency_table = ','.join('{}'.format(args) for args in conversion_rates)
        return '(VALUES {}) AS currency_table(company_id, rate, precision)'.format(currency_table)
    
    @api.model
    def _query_liquidity_lines(self, options):
        """ Compute the balance of all liquidity accounts to populate the following sections:
            'Cash and cash equivalents, beginning of period' and 'Cash and cash equivalents, closing balance'.
        :param options: The query options.
        :return: A list of dictionary (account_id, account_code, account_name, balance).
        """
        if not options.get('date'):
            return []
        currency_table_query = self._get_currency_table(options)
        query = """
                        SELECT
                            account_move_line.account_id as account_id,
                            account.code AS account_code,
                            account.name AS account_name,
                            COALESCE(SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)), 0.0) as amount
                        FROM account_account account
                        LEFT JOIN account_move_line ON account.id = account_move_line.account_id
                        LEFT JOIN {} ON currency_table.company_id = account_move_line.company_id
                        JOIN account_move ON account_move_line.move_id = account_move.id
                        WHERE account.internal_type = 'liquidity' AND account_move_line.date <= '{}' AND account_move.state = 'posted'
                        GROUP BY account_move_line.account_id, account.code, account.name
                        ORDER BY amount DESC
                    """.format(currency_table_query, options['date'])
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()
    
    def get_opening_balance(self, to_date):
        """
        Calculate the total opening bank balance of a period in the cash flow projection report
        @param to_date: the date to calculate the total balance
        @return: the amount for the opening bank balance
        """
        if not to_date:
            return 0.0
        opening_liquidity_lines = self._query_liquidity_lines({
            'date': to_date,
        })
        return sum(line['amount'] for line in opening_liquidity_lines)
    
    def get_cash_in_lines(self, from_date, to_date, options={}):
        """
        Query the cash in lines from account move lines
        @param from_date:   the beginning date of the period
        @param to_date:     the ending date of the period
        @param options:     options for filtering records
        @return: list of dictionary, each element in the list is a cash in line
        """
        query = self._query_cash_in_lines(from_date, to_date, options)
        if query:
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()
            return result
        return []
    
    def get_cash_out_lines(self, from_date, to_date, options={}):
        """
        Query the cash out lines from account move lines
        @param from_date: the beginning date of the period
        @param to_date: the ending date of the period
        @param options: options for filtering records
        @return: list of dictionary, each element in the list is a cash out line
        """
        
        query = self._query_cash_out_lines(from_date, to_date, options)
        if query:
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()
            return result
        return []
    
    ####################################################################################################################
    #                                       QUERY CASH IN LINES                                                        #
    ####################################################################################################################
    
    def _query_cash_in_lines(self, from_date, to_date, options={}):
        """
        Generate selection statement for querying cash flow projection lines
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :param options: options for filtering records
        :return: string of the selection statement
        """
        
        query_table = self._query_table_cash_in(from_date, to_date, options)
        if len(query_table) == 0:
            return """"""
        from_stmt = "({})".format(query_table[0])
        if len(query_table) > 1:
            for stmt in query_table[1:]:
                from_stmt = from_stmt + " UNION ALL ({})".format(stmt)
        
        query_stmt = """
                                SELECT temp.id as transaction_code, temp.name as transaction_name, ROUND(SUM(temp.amount),2) as amount
                                FROM ({}) temp
                                GROUP BY temp.id, temp.name
                                ORDER BY temp.id ASC
                """.format(from_stmt)
        return query_stmt
    
    def _query_table_cash_in(self, from_date, to_date, options={}):
        """
        Generate array of query statements in type of cash in which user wanted to show in the cash flow projection
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :param options: options for filtering records
        :return: array that contains selection statements
        """
        query_table = []
        if not options or not options.get('cash_in') or not from_date or not to_date:
            return query_table
        saved_configurations = options['cash_in']
        cash_in_options = {}
        for configuration in saved_configurations:
            cash_in_options[configuration['code']] = configuration['is_show']
        
        if cash_in_options.get('future_customer_payment'):
            query_table.append(self._query_incoming_payment_lines(from_date, to_date))
        if cash_in_options.get('sale_order'):
            query_table.append(
                self._query_so_lines(from_date, to_date))
        if cash_in_options.get('ar_credit_note'):
            query_table.append(self._query_ar_credit_note_lines(from_date, to_date))
        if cash_in_options.get('ar_invoice'):
            query_table.append(self._query_ar_invoice_lines(from_date, to_date))
        if cash_in_options.get('cash_in_other'):
            query_table.append(self._query_other_cash_in_lines(from_date, to_date))
        
        return query_table
    
    def _query_incoming_payment_lines(self, from_date, to_date):
        """
        Generate statement for querying incoming payment lines
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        companies = self._get_companies()
        # The first period
        today = datetime.datetime.today().date()
        if from_date <= today <= to_date:
            from_date = today + relativedelta(days=1)
        # The past due transactions
        elif to_date < today:
            to_date = from_date - relativedelta(days=1)
        query_incoming_payment_lines = """
            SELECT cast('future_customer_payment' as text) as id, cast('Future Customer Payments' as text) as name, aml.debit as amount, am.name as account_name, TO_CHAR(aml.date + aa.payment_lead_time, 'mm/dd/yyyy') as date, aml.id as line_id, aa.id as account_id, rp.name as partner_name
            FROM account_move_line aml
                     JOIN account_account aa ON aml.account_id = aa.id
                     JOIN account_account_type aat ON aa.user_type_id = aat.id
                     JOIN account_move am ON aml.move_id = am.id
                     LEFT JOIN res_partner rp ON aml.partner_id = rp.id
            WHERE am.state = 'posted'
                     AND aml.debit > 0
                     AND (aml.date + aa.payment_lead_time) >= '{}'
                     AND (aml.date + aa.payment_lead_time) <= '{}'
                     AND aat.type = 'liquidity'
                     AND aml.company_id IN {}
        """.format(from_date, to_date, companies)
        return query_incoming_payment_lines
    
    def _query_so_lines(self, from_date, to_date):
        """
        Generate statement for querying Sale Order's remaining amount
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        companies = self._get_companies()
        so_lead_time = self.env.company.customer_payment_lead_time
        query_so_lines = """
             SELECT cast('sale_order' as text) as id, cast('Sales' as text) as name, so.amount_so_remaining as amount, so.name as account_name, TO_CHAR(so.date_order + interval '{}' day, 'mm/dd/yyyy') as date, so.id as line_id, so.id as account_id, rp.name as partner_name
             FROM sale_order so LEFT JOIN res_partner rp ON so.partner_id = rp.id
             WHERE state NOT IN ('draft', 'cancel')
                            AND amount_so_remaining > 0
                            AND cast((date_order + interval '{}' day) as date) >= '{}'
                            AND cast((date_order + interval '{}' day) as date) <= '{}'
                            AND so.company_id IN {}
        """.format(so_lead_time, so_lead_time, from_date, so_lead_time, to_date, companies)
        return query_so_lines
    
    def _query_ar_invoice_lines(self, from_date, to_date):
        """
        Generate statement for querying Account Receivable invoice lines
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        companies = self._get_companies()
        query_ar_invoice_lines = """
            SELECT cast('ar_invoice' as text) as id, cast('Receivable' as text) as name, aml1.amount_residual as amount, am.name as account_name, TO_CHAR(aml1.date_maturity, 'mm/dd/yyyy') as date, aml1.id as line_id, aml1.account_id, aml1.partner_name
            FROM
                (SELECT aml.amount_residual, aml.move_id, aml.date_maturity, aml.id, aa.id as account_id, rp.name as partner_name
                 FROM account_move_line aml JOIN account_account aa ON aml.account_id = aa.id
                    LEFT JOIN res_partner rp ON aml.partner_id = rp.id
                 WHERE aa.internal_type = 'receivable'
                           AND aml.date_maturity >= '{}'
                           AND aml.date_maturity <= '{}'
                           AND aml.amount_residual > 0
                           AND aml.company_id IN {}) aml1
               JOIN account_move am ON aml1.move_id = am.id
            WHERE am.state = 'posted'
        """.format(from_date, to_date, companies)
        return query_ar_invoice_lines
    
    def _query_ar_credit_note_lines(self, from_date, to_date):
        """
        Generate statement for querying Account Receivable credit note lines
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        companies = self._get_companies()
        query_ar_credit_note_lines = """
            SELECT cast('ar_credit_note' as text) as id, cast('Customer Credit Notes' as text) as name, aml1.amount_residual as amount, am.name as account_name, TO_CHAR(aml1.date_maturity, 'mm/dd/yyyy') as date, aml1.id as line_id, aml1.account_id, aml1.partner_name
            FROM
                (SELECT aml.amount_residual, aml.move_id, aml.date_maturity, aml.id, aa.id as account_id, rp.name as partner_name
                 FROM account_move_line aml JOIN account_account aa ON aml.account_id = aa.id
                    LEFT JOIN res_partner rp ON aml.partner_id = rp.id
                 WHERE aa.internal_type = 'receivable'
                        AND aml.date_maturity >= '{}'
                        AND aml.date_maturity <= '{}'
                        AND aml.amount_residual < 0
                        AND aml.company_id IN {}) aml1
              JOIN account_move am ON aml1.move_id = am.id
            WHERE am.state = 'posted'
                AND am.id NOT IN (
                    SELECT distinct am2.id
                    FROM account_move_line aml
                         JOIN account_move am2 ON aml.move_id = am2.id
                         JOIN account_account aa ON aml.account_id = aa.id
                         JOIN account_account_type aat ON aa.user_type_id = aat.id
                    WHERE am.state = 'posted'
                         AND aml.debit > 0
                         AND aat.type = 'liquidity'
                )
        """.format(from_date, to_date, companies)
        return query_ar_credit_note_lines
    
    def _query_other_cash_in_lines(self, from_date, to_date):
        """
        Generate statement for querying other cash in lines which was typed and saved by users
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        query_other_lines = """SELECT cast('cash_in_other' as text) as id, cast('Others' as text) as name, cast('0' as int) as amount,
                cast('Others' as text) as account_name, null as date, cast('0' as int) as line_id, cast('0' as int) as account_id,
                null as partner_name
        """
        return query_other_lines
    
    ####################################################################################################################
    #                                       QUERY CASH OUT LINES                                                       #
    ####################################################################################################################
    
    def _query_cash_out_lines(self, from_date, to_date, options={}):
        """
        Generate statement for querying cash out lines
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :param options: options for filtering records
        :return: string of the selection statement
        """
        query_table = self._query_table_cash_out(from_date, to_date, options)
        if len(query_table) == 0:
            return """"""
        from_stmt = "({})".format(query_table[0])
        if len(query_table) > 1:
            for table in query_table[1:]:
                from_stmt = from_stmt + " UNION ALL ({})".format(table)
        
        query_stmt = """
            SELECT temp.id as transaction_code, temp.name as transaction_name, ROUND(SUM(temp.amount),2) as amount
            FROM ({}) temp
            GROUP BY temp.id, temp.name
            ORDER BY temp.id ASC
        """.format(from_stmt)
        return query_stmt
    
    def _query_table_cash_out(self, from_date, to_date, options={}):
        """
        Generate array of query statements in type of cash out which user wanted to show in the cash flow projection
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :param options: options for filtering records
        :return: array that contains selection statements
        """
        query_table = []
        if not options or not options.get('cash_out'):
            return []
        saved_configurations = options['cash_out']
        cash_out_options = {}
        for configuration in saved_configurations:
            cash_out_options[configuration['code']] = configuration['is_show']
        if cash_out_options.get('future_vendor_payment'):
            query_table.append(
                self._query_outgoing_payment_lines(from_date, to_date))
        if cash_out_options.get('purchase_order'):
            query_table.append(self._query_po_lines(from_date, to_date))
        if cash_out_options.get('ap_credit_note'):
            query_table.append(self._query_ap_credit_note_lines(from_date, to_date))
        if cash_out_options.get('ap_invoice'):
            query_table.append(self._query_ap_invoice_lines(from_date, to_date))
        if cash_out_options.get('cash_out_other'):
            query_table.append(
                self._query_other_cash_out_lines(from_date, to_date))
        return query_table
    
    def _query_outgoing_payment_lines(self, from_date, to_date):
        """
        Generate statement for querying outgoing payments
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        companies = self._get_companies()
        # The first period
        today = datetime.datetime.today().date()
        if from_date <= today <= to_date:
            from_date = today + relativedelta(days=1)
        # The past due transactions
        elif to_date < today:
            to_date = from_date - relativedelta(days=1)
        query_outgoing_payment_lines = """
            SELECT cast('future_vendor_payment' as text) as id, cast('Future Vendor Payments' as text) as name, aml.credit as amount, am.name as account_name, TO_CHAR(aml.date + aa.payment_lead_time, 'mm/dd/yyyy') as date, aml.id as line_id, aa.id as account_id, rp.name as partner_name
            FROM account_move_line aml
                      JOIN account_account aa ON aml.account_id = aa.id
                      JOIN account_account_type aat ON aa.user_type_id = aat.id
                      JOIN account_move am ON aml.move_id = am.id
                      LEFT JOIN res_partner rp ON aml.partner_id = rp.id
            WHERE am.state = 'posted'
                      AND aml.credit > 0
                      AND (aml.date + aa.payment_lead_time) >= '{}'
                      AND (aml.date + aa.payment_lead_time) <= '{}'
                      AND aat.type = 'liquidity'
                      AND aml.company_id IN {}
        """.format(from_date, to_date, companies)
        return query_outgoing_payment_lines
    
    def _query_po_lines(self, from_date, to_date):
        """
        Generate statement for querying Purchase Order's remaining amount
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        companies = self._get_companies()
        po_lead_time = self.env.company.vendor_payment_lead_time
        query_po_lines = """
            SELECT cast('purchase_order' as text) as id, cast('Purchases' as text) as name, po.amount_so_remaining as amount, po.name as account_name, TO_CHAR(po.date_approve + interval '{}' day, 'mm/dd/yyyy') as date, po.id as line_id, po.id as account_id, rp.name as partner_name
            FROM purchase_order po LEFT JOIN res_partner rp ON po.partner_id = rp.id
            WHERE state NOT IN ('draft', 'cancel')
                       AND amount_so_remaining > 0
                       AND cast((date_approve + interval '{}' day) as date) >= '{}'
                       AND cast((date_approve + interval '{}' day) as date) <= '{}'
                       AND po.company_id IN {}
        """.format(po_lead_time, po_lead_time, from_date, po_lead_time, to_date, companies)
        return query_po_lines
    
    def _query_ap_invoice_lines(self, from_date, to_date):
        """
        Generate statement for querying Account Payable invoice lines
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        companies = self._get_companies()
        query_ap_invoice_lines = """
            SELECT cast('ap_invoice' as text) as id, cast('Payable' as text) as name, -aml1.amount_residual as amount, am.name as account_name, TO_CHAR(aml1.date_maturity, 'mm/dd/yyyy') as date, aml1.id as line_id, aml1.account_id, aml1.partner_name
            FROM
                (SELECT aml.amount_residual, aml.move_id, aml.date_maturity, aml.id, aa.id as account_id, rp.name as partner_name
                 FROM account_move_line aml JOIN account_account aa ON aml.account_id = aa.id
                    LEFT JOIN res_partner rp ON aml.partner_id = rp.id
                 WHERE aa.internal_type = 'payable'
                          AND aml.date_maturity >= '{}'
                          AND aml.date_maturity <= '{}'
                          AND aml.amount_residual < 0
                          AND aml.company_id IN {}) aml1
               JOIN account_move am ON aml1.move_id = am.id
            WHERE am.state = 'posted'
        """.format(from_date, to_date, companies)
        return query_ap_invoice_lines
    
    def _query_ap_credit_note_lines(self, from_date, to_date):
        """
        Generate statement for querying Account Payable credit note lines
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        companies = self._get_companies()
        query_ap_credit_note_lines = """
           SELECT cast('ap_credit_note' as text) as id, cast('Vendor Credit Notes' as text) as name, -aml1.amount_residual as amount, am.name as account_name, TO_CHAR(aml1.date_maturity, 'mm/dd/yyyy') as date, aml1.id as line_id, aml1.account_id, aml1.partner_name
           FROM
               (SELECT aml.amount_residual, aml.move_id, aml.date_maturity, aml.id, aa.id as account_id, rp.name as partner_name
                FROM account_move_line aml JOIN account_account aa ON aml.account_id = aa.id
                    LEFT JOIN res_partner rp ON aml.partner_id = rp.id
                WHERE aa.internal_type = 'payable'
                        AND aml.date_maturity >= '{}'
                        AND aml.date_maturity <= '{}'
                        AND aml.amount_residual > 0
                        AND aml.company_id IN {}) aml1
              JOIN account_move am ON aml1.move_id = am.id
           WHERE am.state = 'posted'
                AND am.id NOT IN (
                    SELECT distinct am2.id
                    FROM account_move_line aml
                         JOIN account_move am2 ON aml.move_id = am2.id
                         JOIN account_account aa ON aml.account_id = aa.id
                         JOIN account_account_type aat ON aa.user_type_id = aat.id
                    WHERE am.state = 'posted'
                         AND aml.credit > 0
                         AND aat.type = 'liquidity'
                )
        """.format(from_date, to_date, companies)
        return query_ap_credit_note_lines
    
    def _query_other_cash_out_lines(self, from_date, to_date):
        """
        Generate statement for querying other cash in lines which was typed and saved by users
        :param from_date: the beginning date of the period
        :param to_date: the ending date of the period
        :return: string the selection statement
        """
        query_other_lines = """SELECT cast('cash_out_other' as text) as id, cast('Others' as text) as name, cast('0' as int) as amount,
                cast('Others' as text) as account_name, null as date, cast('0' as int) as line_id, cast('0' as int) as account_id,
                null as partner_name
        """
        return query_other_lines
