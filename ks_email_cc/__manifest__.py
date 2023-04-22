# -*- coding: utf-8 -*-
{
    'name': "Email Cc and Bcc",

    'summary': """
            Email Cc and Bcc apps allows a user to send mail in mail composer keeping partner's or emails directly in Cc and Bcc
        """,

    'description': """
    """,

    'author': "Ksolves India Ltd.",
    'website': "https://www.ksolves.com/",
    'category': 'Tools',
    'license': 'LGPL-3',
    'currency': 'USD',
    'price': 0.0,
    # "live_test_url":  "http://saastoolkit.kappso.in/",
    'version': '14.0.1.0.1',
    'maintainer': 'Ksolves India Ltd.',
    'support': 'sales@ksolves.com',
    'installable': True,
    'application': True,
    'sequence': 1,
    'depends': ['base','web','mail','account'],
    'images': [
        "static/description/email_cc_banner.gif",
    ],
    'data': [
        'wizard/ks_message_compose_inherit.xml',
        'wizard/ks_message_compose_inherit1.xml',
        'views/ks_res_company_inherit.xml',
        'views/ks_web_assets.xml'
    ],

    'qweb': [
           'static/src/xml/ks_templates_inherit.xml',
    ],

}
