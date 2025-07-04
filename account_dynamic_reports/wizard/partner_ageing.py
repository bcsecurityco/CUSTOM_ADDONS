from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, date
import calendar
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import json
import io
from odoo.tools import date_utils

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

FETCH_RANGE = 2500

DATE_DICT = {
    '%m/%d/%Y' : 'mm/dd/yyyy',
    '%Y/%m/%d' : 'yyyy/mm/dd',
    '%m/%d/%y' : 'mm/dd/yy',
    '%d/%m/%Y' : 'dd/mm/yyyy',
    '%d/%m/%y' : 'dd/mm/yy',
    '%d-%m-%Y' : 'dd-mm-yyyy',
    '%d-%m-%y' : 'dd-mm-yy',
    '%m-%d-%Y' : 'mm-dd-yyyy',
    '%m-%d-%y' : 'mm-dd-yy',
    '%Y-%m-%d' : 'yyyy-mm-dd',
    '%f/%e/%Y' : 'm/d/yyyy',
    '%f/%e/%y' : 'm/d/yy',
    '%e/%f/%Y' : 'd/m/yyyy',
    '%e/%f/%y' : 'd/m/yy',
    '%f-%e-%Y' : 'm-d-yyyy',
    '%f-%e-%y' : 'm-d-yy',
    '%e-%f-%Y' : 'd-m-yyyy',
    '%e-%f-%y' : 'd-m-yy'
}

class InsPartnerAgeing(models.TransientModel):
    _name = "ins.partner.ageing"

    @api.onchange('partner_type')
    def onchange_partner_type(self):
        self.partner_ids = [(5,)]
        if self.partner_type:
            if self.partner_type == 'customer':
                partner_company_domain = [('parent_id', '=', False),
                                          ('customer_rank', '>', 0),
                                          '|',
                                          ('company_id', '=', self.env.company.id),
                                          ('company_id', '=', False)]

                self.partner_ids |= self.env['res.partner'].search(partner_company_domain)
            if self.partner_type == 'supplier':
                partner_company_domain = [('parent_id', '=', False),
                                          ('supplier_rank', '>', 0),
                                          '|',
                                          ('company_id', '=', self.env.company.id),
                                          ('company_id', '=', False)]

                self.partner_ids |= self.env['res.partner'].search(partner_company_domain)

    def name_get(self):
        res = []
        for record in self:
            res.append((record.id, 'Ageing'))
        return res

    as_on_date = fields.Date(string='As on date', required=True, default=fields.Date.today())
    bucket_1 = fields.Integer(string='Bucket 1', required=True, default=lambda self:self.env.company.bucket_1)
    bucket_2 = fields.Integer(string='Bucket 2', required=True, default=lambda self:self.env.company.bucket_2)
    bucket_3 = fields.Integer(string='Bucket 3', required=True, default=lambda self:self.env.company.bucket_3)
    bucket_4 = fields.Integer(string='Bucket 4', required=True, default=lambda self:self.env.company.bucket_4)
    bucket_5 = fields.Integer(string='Bucket 5', required=True, default=lambda self:self.env.company.bucket_5)
    include_details = fields.Boolean(string='Include Details', default=True)
    type = fields.Selection([('receivable','Receivable Accounts Only'),
                              ('payable','Payable Accounts Only')], string='Type')
    partner_type = fields.Selection([('customer', 'Customer Only'),
                             ('supplier', 'Supplier Only')], string='Partner Type')

    partner_ids = fields.Many2many(
        'res.partner', required=False
    )
    partner_category_ids = fields.Many2many(
        'res.partner.category', string='Partner Tag',
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company
    )

    def write(self, vals):
        if not vals.get('partner_ids'):
            vals.update({
                'partner_ids': [(5, 0, 0)]
            })

        if vals.get('partner_category_ids'):
            vals.update({'partner_category_ids': vals.get('partner_category_ids')})
        if vals.get('partner_category_ids') == []:
            vals.update({'partner_category_ids': [(5,)]})

        ret = super(InsPartnerAgeing, self).write(vals)
        return ret

    def validate_data(self):
        if not(self.bucket_1 < self.bucket_2 and self.bucket_2 < self.bucket_3 and self.bucket_3 < self.bucket_4 and \
            self.bucket_4 < self.bucket_5):
            raise ValidationError(_('"Bucket order must be ascending"'))
        return True

    def get_filters(self, default_filters={}):

        partner_company_domain = [('parent_id','=', False),
                                  '|',
                                  ('customer_rank', '>', 0),
                                  ('supplier_rank', '>', 0),
                                  '|',
                                  ('company_id', '=', self.env.company.id),
                                  ('company_id', '=', False)]

        partners = self.partner_ids if self.partner_ids else self.env['res.partner'].search(partner_company_domain)
        categories = self.partner_category_ids if self.partner_category_ids else self.env['res.partner.category'].search([])

        filter_dict = {
            'partner_ids': self.partner_ids.ids,
            'partner_category_ids': self.partner_category_ids.ids,
            'company_id': self.company_id and self.company_id.id or False,
            'as_on_date': self.as_on_date,
            'type': self.type,
            'partner_type': self.partner_type,
            'bucket_1': self.bucket_1,
            'bucket_2': self.bucket_2,
            'bucket_3': self.bucket_3,
            'bucket_4': self.bucket_4,
            'bucket_5': self.bucket_5,
            'include_details': self.include_details,

            'partners_list': [(p.id, p.name) for p in partners],
            'category_list': [(c.id, c.name) for c in categories],
            'company_name': self.company_id and self.company_id.name,
        }
        filter_dict.update(default_filters)
        return filter_dict

    def process_filters(self):
        ''' To show on report headers'''

        data = self.get_filters(default_filters={})

        filters = {}

        filters['bucket_1'] = data.get('bucket_1')
        filters['bucket_2'] = data.get('bucket_2')
        filters['bucket_3'] = data.get('bucket_3')
        filters['bucket_4'] = data.get('bucket_4')
        filters['bucket_5'] = data.get('bucket_5')

        if data.get('partner_ids', []):
            filters['partners'] = self.env['res.partner'].browse(data.get('partner_ids', [])).mapped('name')
        else:
            filters['partners'] = ['All']

        if data.get('as_on_date', False):
            filters['as_on_date'] = data.get('as_on_date')

        if data.get('company_id'):
            filters['company_id'] = data.get('company_id')
        else:
            filters['company_id'] = ''

        if data.get('type'):
            filters['type'] = data.get('type')

        if data.get('partner_type'):
            filters['partner_type'] = data.get('partner_type')

        if data.get('partner_category_ids', []):
            filters['categories'] = self.env['res.partner.category'].browse(data.get('partner_category_ids', [])).mapped('name')
        else:
            filters['categories'] = ['All']

        if data.get('include_details'):
            filters['include_details'] = True
        else:
            filters['include_details'] = False

        filters['partners_list'] = data.get('partners_list')
        filters['category_list'] = data.get('category_list')
        filters['company_name'] = data.get('company_name')

        return filters

    def prepare_bucket_list(self):
        periods = {}
        date_from = self.as_on_date
        date_from = fields.Date.from_string(date_from)

        lang = self.env.user.lang
        language_id = self.env['res.lang'].search([('code', '=', lang)])[0]

        bucket_list = [self.bucket_1,self.bucket_2,self.bucket_3,self.bucket_4,self.bucket_5]

        start = False
        stop = date_from
        name = 'Not Due'
        periods[0] = {
            'bucket': 'As on',
            'name': name,
            'start': '',
            'stop': stop.strftime('%Y-%m-%d'),
        }

        stop = date_from
        final_date = False
        for i in range(5):
            start = stop - relativedelta(days=1)
            stop = start - relativedelta(days=bucket_list[i])
            name = '0 - ' + str(bucket_list[0]) if i==0 else  str(str(bucket_list[i-1] + 1)) + ' - ' + str(bucket_list[i])
            final_date = stop
            periods[i+1] = {
                'bucket': bucket_list[i],
                'name': name,
                'start': start.strftime('%Y-%m-%d'),
                'stop': stop.strftime('%Y-%m-%d'),
            }

        start = final_date -relativedelta(days=1)
        stop = ''
        name = str(self.bucket_5) + ' +'

        periods[6] = {
            'bucket': 'Above',
            'name': name,
            'start': start.strftime('%Y-%m-%d'),
            'stop': '',
        }
        return periods

    def process_detailed_data(self, offset=0, partner=0, fetch_range=FETCH_RANGE):
        '''

        It is used for showing detailed move lines as sub lines. It is defered loading compatable
        :param offset: It is nothing but page numbers. Multiply with fetch_range to get final range
        :param partner: Integer - Partner
        :param fetch_range: Global Variable. Can be altered from calling model
        :return: count(int-Total rows without offset), offset(integer), move_lines(list of dict)
        '''
        as_on_date = self.as_on_date
        period_dict = self.prepare_bucket_list()
        period_list = [period_dict[a]['name'] for a in period_dict]
        company_id = self.env.company

        type = ('receivable','payable')
        if self.type:
            type = tuple([self.type,'none'])

        offset = offset * fetch_range
        count = 0

        if partner:


            sql = """
                    SELECT COUNT(*)
                    FROM
                        account_move_line AS l
                    LEFT JOIN
                        account_move AS m ON m.id = l.move_id
                    LEFT JOIN
                        account_account AS a ON a.id = l.account_id
                    LEFT JOIN
                        account_account_type AS ty ON a.user_type_id = ty.id
                    LEFT JOIN
                        account_journal AS j ON l.journal_id = j.id
                    WHERE
                        l.balance <> 0
                        AND m.state = 'posted'
                        AND ty.type IN %s
                        AND l.partner_id = %s
                        AND l.date <= '%s'
                        AND l.company_id = %s
                """ % (type, partner, as_on_date, company_id.id)
            self.env.cr.execute(sql)
            count = self.env.cr.fetchone()[0]

            SELECT = """SELECT m.name AS move_name,
                                m.id AS move_id,
                                l.date AS date,
                                l.date_maturity AS date_maturity, 
                                j.name AS journal_name,
                                cc.id AS company_currency_id,
                                m.ref AS reference,
                                m.num_auto AS autorizacion,
                                m.num_rips AS rips,
                                m.amount_untaxed AS subtotal,
                                m.ei_amount_tax_no_withholding AS iva,
                                m.ei_amount_tax_withholding AS retenciones,
                                m.amount_residual AS residual,
                                a.name AS account_name, """

            for period in period_dict:
                if period_dict[period].get('start') and period_dict[period].get('stop'):
                    SELECT += """ CASE 
                                    WHEN 
                                        COALESCE(l.date_maturity,l.date) >= '%s' AND 
                                        COALESCE(l.date_maturity,l.date) <= '%s'
                                    THEN
                                        sum(l.balance) +
                                        sum(
                                            COALESCE(
                                                (SELECT 
                                                    SUM(amount)
                                                FROM account_partial_reconcile
                                                WHERE credit_move_id = l.id AND max_date <= '%s'), 0
                                                )
                                            ) -
                                        sum(
                                            COALESCE(
                                                (SELECT 
                                                    SUM(amount) 
                                                FROM account_partial_reconcile 
                                                WHERE debit_move_id = l.id AND max_date <= '%s'), 0
                                                )
                                            )
                                    ELSE
                                        0
                                    END AS %s,"""%(period_dict[period].get('stop'),
                                                   period_dict[period].get('start'),
                                                   as_on_date,
                                                   as_on_date,
                                                   'range_'+str(period),
                                                   )
                elif not period_dict[period].get('start'):
                    SELECT += """ CASE 
                                    WHEN 
                                        COALESCE(l.date_maturity,l.date) >= '%s' 
                                    THEN
                                        sum(
                                            l.balance
                                            ) +
                                        sum(
                                            COALESCE(
                                                (SELECT 
                                                    SUM(amount)
                                                FROM account_partial_reconcile
                                                WHERE credit_move_id = l.id AND max_date <= '%s'), 0
                                                )
                                            ) -
                                        sum(
                                            COALESCE(
                                                (SELECT 
                                                    SUM(amount) 
                                                FROM account_partial_reconcile 
                                                WHERE debit_move_id = l.id AND max_date <= '%s'), 0
                                                )
                                            )
                                    ELSE
                                        0
                                    END AS %s,"""%(period_dict[period].get('stop'), as_on_date, as_on_date, 'range_'+str(period))
                else:
                    SELECT += """ CASE
                                    WHEN
                                        COALESCE(l.date_maturity,l.date) <= '%s' 
                                    THEN
                                        sum(
                                            l.balance
                                            ) +
                                        sum(
                                            COALESCE(
                                                (SELECT 
                                                    SUM(amount)
                                                FROM account_partial_reconcile
                                                WHERE credit_move_id = l.id AND max_date <= '%s'), 0
                                                )
                                            ) -
                                        sum(
                                            COALESCE(
                                                (SELECT 
                                                    SUM(amount) 
                                                FROM account_partial_reconcile 
                                                WHERE debit_move_id = l.id AND max_date <= '%s'), 0
                                                )
                                            )
                                    ELSE
                                        0
                                    END AS %s """%(period_dict[period].get('start'), as_on_date, as_on_date ,'range_'+str(period))

            sql = """
                    FROM
                        account_move_line AS l
                    LEFT JOIN
                        account_move AS m ON m.id = l.move_id
                    LEFT JOIN
                        account_account AS a ON a.id = l.account_id
                    LEFT JOIN
                        account_account_type AS ty ON a.user_type_id = ty.id
                    LEFT JOIN
                        account_journal AS j ON l.journal_id = j.id
                    LEFT JOIN 
                        res_currency AS cc ON l.company_currency_id = cc.id
                    WHERE
                        l.balance <> 0
                        AND m.state = 'posted'
                        AND ty.type IN %s
                        AND l.partner_id = %s
                        AND l.date <= '%s'
                        AND l.company_id = %s
                    GROUP BY
                        l.date, l.date_maturity, m.id, m.name, j.name, a.name, cc.id, m.amount_untaxed, m.amount_residual, m.ref, m.num_rips, m.num_auto, m.ei_amount_tax_no_withholding, m.ei_amount_tax_withholding 
                    OFFSET %s ROWS
                    FETCH FIRST %s ROWS ONLY
                """%(type, partner, as_on_date, company_id.id, offset, fetch_range)
            self.env.cr.execute(SELECT + sql)
            final_list = self.env.cr.dictfetchall() or 0.0
            move_lines = []
            for m in final_list:
                if (m['range_0'] or m['range_1'] or m['range_2'] or m['range_3'] or m['range_4'] or m['range_5']):
                    move_lines.append(m)

            if move_lines:
                return count, offset, move_lines, period_list
            else:
                return 0, 0, [], []

    def process_data(self):
        ''' Query Start Here
        ['partner_id':
            {'0-30':0.0,
            '30-60':0.0,
            '60-90':0.0,
            '90-120':0.0,
            '>120':0.0,
            'as_on_date_amount': 0.0,
            'total': 0.0}]
        1. Prepare bucket range list from bucket values
        2. Fetch partner_ids and loop through bucket range for values
        '''
        period_dict = self.prepare_bucket_list()

        domain = ['|',('company_id','=',self.env.company.id),('company_id','=',False)]
        if self.partner_type == 'customer':
            domain.append(('customer_rank','>',0))
        if self.partner_type == 'supplier':
            domain.append(('supplier_rank','>',0))

        if self.partner_category_ids:
            domain.append(('category_id','in',self.partner_category_ids.ids))

        partner_ids = self.partner_ids or self.env['res.partner'].search(domain)
        as_on_date = self.as_on_date
        company_currency_id = self.env.company.currency_id.id
        company_id = self.env.company

        type = ('receivable', 'payable')
        if self.type:
            type = tuple([self.type,'none'])

        partner_dict = {}
        for partner in partner_ids:
            partner_dict.update({partner.id:{}})

        partner_dict.update({'Total': {}})
        for period in period_dict:
            partner_dict['Total'].update({period_dict[period]['name']: 0.0})
        partner_dict['Total'].update({'total': 0.0, 'partner_name': 'ZZZZZZZZZ'})
        partner_dict['Total'].update({'company_currency_id': company_currency_id})

        for partner in partner_ids:
            partner_dict[partner.id].update({'partner_name':partner.name})
            total_balance = 0.0

            sql = """
                SELECT
                    COUNT(*) AS count
                FROM
                    account_move_line AS l
                LEFT JOIN
                    account_move AS m ON m.id = l.move_id
                LEFT JOIN
                    account_account AS a ON a.id = l.account_id
                LEFT JOIN
                    account_account_type AS ty ON a.user_type_id = ty.id
                WHERE
                    l.balance <> 0
                    AND m.state = 'posted'
                    AND ty.type IN %s
                    AND l.partner_id = %s
                    AND l.date <= '%s'
                    AND l.company_id = %s
            """%(type, partner.id, as_on_date, company_id.id)
            self.env.cr.execute(sql)
            fetch_dict = self.env.cr.dictfetchone() or 0.0
            count = fetch_dict.get('count') or 0.0

            if count:
                for period in period_dict:

                    where = " AND l.date <= '%s' AND l.partner_id = %s AND COALESCE(l.date_maturity,l.date) "%(as_on_date, partner.id)
                    if period_dict[period].get('start') and period_dict[period].get('stop'):
                        where += " BETWEEN '%s' AND '%s'" % (period_dict[period].get('stop'), period_dict[period].get('start'))
                    elif not period_dict[period].get('start'): # ie just
                        where += " >= '%s'" % (period_dict[period].get('stop'))
                    else:
                        where += " <= '%s'" % (period_dict[period].get('start'))

                    sql = """
                        SELECT
                            sum(
                                l.balance
                                ) AS balance,
                            sum(
                                COALESCE(
                                    (SELECT 
                                        SUM(amount)
                                    FROM account_partial_reconcile
                                    WHERE credit_move_id = l.id AND max_date <= '%s'), 0
                                    )
                                ) AS sum_debit,
                            sum(
                                COALESCE(
                                    (SELECT 
                                        SUM(amount) 
                                    FROM account_partial_reconcile 
                                    WHERE debit_move_id = l.id AND max_date <= '%s'), 0
                                    )
                                ) AS sum_credit
                        FROM
                            account_move_line AS l
                        LEFT JOIN
                            account_move AS m ON m.id = l.move_id
                        LEFT JOIN
                            account_account AS a ON a.id = l.account_id
                        LEFT JOIN
                            account_account_type AS ty ON a.user_type_id = ty.id
                        WHERE
                            l.balance <> 0
                            AND m.state = 'posted'
                            AND ty.type IN %s
                            AND l.company_id = %s
                    """%(as_on_date, as_on_date, type, company_id.id)
                    amount = 0.0
                    self.env.cr.execute(sql + where)
                    fetch_dict = self.env.cr.dictfetchall() or 0.0

                    if not fetch_dict[0].get('balance'):
                        amount = 0.0
                    else:
                        amount = fetch_dict[0]['balance'] + fetch_dict[0]['sum_debit'] - fetch_dict[0]['sum_credit']
                        total_balance += amount

                    partner_dict[partner.id].update({period_dict[period]['name']:amount})
                    partner_dict['Total'][period_dict[period]['name']] += amount
                partner_dict[partner.id].update({'count': count})
                partner_dict[partner.id].update({'pages': self.get_page_list(count)})
                partner_dict[partner.id].update({'single_page': True if count <= FETCH_RANGE else False})
                partner_dict[partner.id].update({'total': total_balance})
                partner_dict['Total']['total'] += total_balance
                partner_dict[partner.id].update({'company_currency_id': company_currency_id})
                partner_dict['Total'].update({'company_currency_id': company_currency_id})
            else:
                partner_dict.pop(partner.id, None)
        return period_dict, partner_dict

    def get_page_list(self, total_count):
        '''
        Helper function to get list of pages from total_count
        :param total_count: integer
        :return: list(pages) eg. [1,2,3,4,5,6,7 ....]
        '''
        page_count = int(total_count / FETCH_RANGE)
        if total_count % FETCH_RANGE:
            page_count += 1
        return [i+1 for i in range(0, int(page_count))] or []

    def get_report_datas(self, default_filters={}):
        '''
        Main method for pdf, xlsx and js calls
        :param default_filters: Use this while calling from other methods. Just a dict
        :return: All the datas for GL
        '''
        if self.validate_data():
            filters = self.process_filters()
            period_dict, ageing_lines = self.process_data()
            period_list = [period_dict[a]['name'] for a in period_dict]
            return filters, ageing_lines, period_dict, period_list

    def action_pdf(self):
        filters, ageing_lines, period_dict, period_list = self.get_report_datas()
        return self.env.ref(
            'account_dynamic_reports'
            '.action_print_partner_ageing').with_context(landscape=False).report_action(
                self, data={'Ageing_data': ageing_lines,
                        'Filters': filters,
                        'Period_Dict': period_dict,
                        'Period_List': period_list
                        })

    def action_xlsx(self):
        ''' Button function for Xlsx '''

        data = self.read()
        as_on_date = fields.Date.from_string(self.as_on_date).strftime(
            self.env['res.lang'].search([('code', '=', self.env.user.lang)])[0].date_format)

        return {
            'type': 'ir.actions.report',
            'data': {'model': 'ins.partner.ageing',
                     'options': json.dumps(data[0], default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'Ageing as On - %s' % (as_on_date),
                     },
            'report_type': 'xlsx'
        }

    def get_xlsx_report(self, data, response):

        # Initialize
        #############################################################
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Partner Ageing')
        sheet.set_zoom(95)
        sheet_2 = workbook.add_worksheet('Filters')
        sheet_2.protect()

        # Get record and data
        record = self.env['ins.partner.ageing'].browse(data.get('id', [])) or False
        filter, ageing_lines, period_dict, period_list = record.get_report_datas()

        # Formats
        ############################################################
        sheet.set_column(0, 0, 15)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 3, 15)
        sheet.set_column(3, 3, 15)
        sheet.set_column(4, 4, 15)
        sheet.set_column(5, 5, 15)
        sheet.set_column(6, 6, 15)
        sheet.set_column(7, 7, 15)
        sheet.set_column(8, 8, 15)
        sheet.set_column(9, 9, 15)
        sheet.set_column(10, 10, 15)
        sheet.set_column(11, 11, 15)
        sheet.set_column(12, 12, 15)
        sheet.set_column(13, 13, 15)
        sheet.set_column(14, 14, 15)
        sheet.set_column(15, 15, 15)
        sheet.set_column(16, 16, 15)
        sheet.set_column(17, 17, 15)
        

        sheet_2.set_column(0, 0, 35)
        sheet_2.set_column(1, 1, 25)
        sheet_2.set_column(2, 2, 25)
        sheet_2.set_column(3, 3, 25)
        sheet_2.set_column(4, 4, 25)
        sheet_2.set_column(5, 5, 25)
        sheet_2.set_column(6, 6, 25)

        sheet.freeze_panes(4, 0)
        sheet.screen_gridlines = False
        sheet_2.screen_gridlines = False
        sheet_2.protect()
        sheet.set_zoom(75)

        format_title = workbook.add_format({
            'bold': True,
            'align': 'center',
            'font_size': 14,
            'font': 'Arial'
        })
        format_header = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'align': 'center',
            'font': 'Arial'
            # 'border': True
        })
        format_header_period = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'align': 'center',
            'font': 'Arial',
            'left': True,
            'right': True,
            # 'border': True
        })
        content_header = workbook.add_format({
            'bold': False,
            'font_size': 10,
            'align': 'center',
            'font': 'Arial'
        })
        content_header_date = workbook.add_format({
            'bold': False,
            'font_size': 10,
            'align': 'center',
            'font': 'Arial'
            # 'num_format': 'dd/mm/yyyy',
        })
        line_header = workbook.add_format({
            'font_size': 11,
            'align': 'center',
            'bold': True,
            'left': True,
            'right': True,
            'font': 'Arial'
        })
        line_header_total = workbook.add_format({
            'font_size': 11,
            'align': 'center',
            'bold': True,
            'border': True,
            'font': 'Arial'
        })
        line_header_period = workbook.add_format({
            'font_size': 11,
            'align': 'center',
            'bold': True,
            'left': True,
            'right': True,
            'font': 'Arial'
        })
        line_header_light = workbook.add_format({
            'bold': False,
            'font_size': 10,
            'align': 'center',
            'border': False,
            'font': 'Arial',
            'text_wrap': True,
        })
        line_header_light_period = workbook.add_format({
            'bold': False,
            'font_size': 10,
            'align': 'center',
            'left': True,
            'right': True,
            'font': 'Arial',
            'text_wrap': True,
        })
        line_header_light_date = workbook.add_format({
            'bold': False,
            'font_size': 10,
            'border': False,
            'font': 'Arial',
            'align': 'center',
        })

        lang = self.env.user.lang
        lang_id = self.env['res.lang'].search([('code', '=', lang)])[0]
        currency_id = self.env.user.company_id.currency_id
        line_header.num_format = currency_id.excel_format
        line_header_light.num_format = currency_id.excel_format
        line_header_light_period.num_format = currency_id.excel_format
        line_header_total.num_format = currency_id.excel_format
        line_header_light_date.num_format = DATE_DICT.get(lang_id.date_format, 'dd/mm/yyyy')
        content_header_date.num_format = DATE_DICT.get(lang_id.date_format, 'dd/mm/yyyy')

        # Write data
        ################################################################
        row_pos_2 = 0
        row_pos = 0
        sheet.merge_range(0, 0, 0, 11, 'Partner Ageing' + ' - ' + data['company_id'][1], format_title)

        # Write filters
        row_pos_2 += 2
        sheet_2.write(row_pos_2, 0, _('As on Date'), format_header)
        datestring = fields.Date.from_string(str(filter['as_on_date'])).strftime(lang_id.date_format)
        sheet_2.write(row_pos_2, 1, datestring or '', content_header_date)
        row_pos_2 += 1
        sheet_2.write(row_pos_2, 0, _('Partners'), format_header)
        p_list = ', '.join([lt or '' for lt in filter.get('partners')])
        sheet_2.write(row_pos_2, 1, p_list, content_header)
        row_pos_2 += 1
        sheet_2.write(row_pos_2, 0, _('Partner Tag'), format_header)
        p_list = ', '.join([lt or '' for lt in filter.get('categories')])
        sheet_2.write(row_pos_2, 1, p_list, content_header)

        # Write Ledger details
        row_pos += 3
        if record.include_details:
            sheet.write(row_pos, 0,  _('Entry #'), format_header)
            sheet.write(row_pos, 1, _('Due Date'), format_header)
            sheet.write(row_pos, 2, _('Journal'), format_header)
            sheet.write(row_pos, 3, _('Account'), format_header)
            sheet.write(row_pos, 4, _('Autorizacion'), format_header)
            sheet.write(row_pos, 5, _('Rips'), format_header)
            sheet.write(row_pos, 6, _('Subtotal'), format_header)
            sheet.write(row_pos, 7, _('Iva'), format_header)
            sheet.write(row_pos, 8, _('Retencion'), format_header)
            sheet.write(row_pos, 9, _('Saldo'), format_header)
        else:
            sheet.merge_range(row_pos, 0, row_pos, 3, _('Partner'),
                                   format_header)
        k = 10
        for period in period_list:
            sheet.write(row_pos, k, str(period),
                                    format_header_period)
            k += 1
        sheet.write(row_pos, k, _('Total'),
                                format_header_period)
        if ageing_lines:
            for line in ageing_lines:
                # Dummy vacant lines
                row_pos += 1
                sheet.write(row_pos, 10, '', line_header_light_period)
                sheet.write(row_pos, 11, '', line_header_light_period)
                sheet.write(row_pos, 12, '', line_header_light_period)
                sheet.write(row_pos, 13, '', line_header_light_period)
                sheet.write(row_pos, 14, '', line_header_light_period)
                sheet.write(row_pos, 15, '', line_header_light_period)
                sheet.write(row_pos, 16, '', line_header_light_period)
                sheet.write(row_pos, 17, '', line_header_light_period)
                row_pos += 1
                if line != 'Total':
                    sheet.merge_range(row_pos, 0, row_pos, 3, ageing_lines[line].get('partner_name'), line_header)
                else:
                    sheet.merge_range(row_pos, 0, row_pos, 3, _('Total'),line_header_total)
                k = 10
                for period in period_list:
                    if line != 'Total':
                        sheet.write(row_pos, k, ageing_lines[line][period],line_header)
                    else:
                        sheet.write(row_pos, k, ageing_lines[line][period], line_header_total)
                    k += 1
                if line != 'Total':
                    sheet.write(row_pos, k, ageing_lines[line]['total'], line_header)
                else:
                    sheet.write(row_pos, k, ageing_lines[line]['total'], line_header_total)
                if record.include_details:
                    if line != 'Total':
                        count, offset, sub_lines, period_list = record.process_detailed_data(partner=line, fetch_range=1000000)
                        for sub_line in sub_lines:
                            row_pos += 1
                            sheet.write(row_pos, 0, sub_line.get('move_name') or '',
                                                    line_header_light)
                            datestring = fields.Date.from_string(str(sub_line.get('date_maturity') or sub_line.get('date'))).strftime(
                                lang_id.date_format)
                            sheet.write(row_pos, 1, datestring, line_header_light_date)
                            sheet.write(row_pos, 2, sub_line.get('journal_name'), line_header_light)
                            sheet.write(row_pos, 3, sub_line.get('account_name') or '', line_header_light)
                            sheet.write(row_pos, 4, str(sub_line.get('autorizacion')) or '', line_header_light)
                            sheet.write(row_pos, 5, str(sub_line.get('rips')) or '', line_header_light)
                            sheet.write(row_pos, 6, str(sub_line.get('subtotal')) or '', line_header_light)
                            sheet.write(row_pos, 7, str(sub_line.get('iva')) or '', line_header_light)
                            sheet.write(row_pos, 8, str(sub_line.get('retenciones')) or '', line_header_light)
                            sheet.write(row_pos, 9, str(sub_line.get('residual')) or '', line_header_light)
                            sheet.write(row_pos, 10, float(sub_line.get('range_0')), line_header_light_period)
                            sheet.write(row_pos, 11, float(sub_line.get('range_1')), line_header_light_period)
                            sheet.write(row_pos, 12, float(sub_line.get('range_2')), line_header_light_period)
                            sheet.write(row_pos, 13, float(sub_line.get('range_3')), line_header_light_period)
                            sheet.write(row_pos, 14, float(sub_line.get('range_4')), line_header_light_period)
                            sheet.write(row_pos, 15, float(sub_line.get('range_5')), line_header_light_period)
                            sheet.write(row_pos, 16, float(sub_line.get('range_6')), line_header_light_period)
                            sheet.write(row_pos, 17, '', line_header_light_period)
            row_pos += 1
            k = 10

        # Close and return
        #################################################################
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

    def action_view(self):
        res = {
            'type': 'ir.actions.client',
            'name': 'Ageing View',
            'tag': 'dynamic.pa',
            'context': {'wizard_id': self.id}
        }
        return res