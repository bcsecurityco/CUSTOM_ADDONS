# -*- coding: utf-8 -*-
{
    'name': 'All in one Dynamic Financial Reports v14',
    'version': '14.1.0',
    'summary': "General Ledger Trial Balance Ageing Balance Sheet Profit and Loss Cash Flow Dynamic",
    'sequence': 15,
    'description': """
                    informes financieros por  terceros
                    """,
    'category': 'Accounting/Accounting',
    'author': 'servisoft latam',
    'maintainer': 'servisoft latam',
    'website': '',
    'images': ['static/description/banner.gif'],
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
       	'data/data_financial_report.xml',

        'views/views.xml',
        'views/res_company_view.xml',

        'views/general_ledger_view.xml',
        'views/partner_ledger_view.xml',
        'views/trial_balance_view.xml',
        'views/trial_balance_partner_view.xml',
        'views/partner_ageing_view.xml',
        'views/financial_report_view.xml',

        'wizard/general_ledger_view.xml',
        'wizard/partner_ledger_view.xml',
        'wizard/trial_balance_view.xml',
        'wizard/partner_ageing_view.xml',
        'wizard/financial_report_view.xml',
        'wizard/trial_balance_partners_view.xml',

      
    ],
    'demo': [],
    'license': 'OPL-1',
    'qweb': ['static/src/xml/view.xml'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
