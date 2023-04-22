# -*- coding: utf-8 -*-
#################################################################################
# Author      : Ashish Hirpara (<www.ashish-hirpara.com>)
# Copyright(c): 2021
# All Rights Reserved.
#
# This module is copyright property of the author mentioned above.
# You can`t redistribute it.
#
#################################################################################

{
    'name': 'Simplify Access Management | Manage - Hide Menu, Submenu, Fields, Action, Reports, Views | Restrict/Read-Only User, Apps,  Fields, Export, Archive, Actions, Views, Reports, Delete items | Manage Access rights from one place | Role based access right management',
    'version': '14.0.0.0',
    'sequence': 5,
    'author': 'Ashish Hirpara',
    'license': 'OPL-1',
    'category': 'Extra Tools',
    'website': 'https://ashish-hirpara.com/r/odoo',
    'summary': 'All In One Access Management App for setting the correct access rights for fields, models, menus, views for any module and for any user.',
    'description':"""
        All In One Access Management App for setting the correct access rights for fields, models, menus, views for any module and for any user.
        Configuring correct access rights in Odoo is quite technical for someone who has little experience with the system and can get messy if you are not sure what you are doing. This module helps you avoid all this complexity by providing you with a user friendly interface from where you can define access to specific objects in one place such as -

        Model/App access (Reports, Actions, Views, Readonly, Create, Write, Delete, Export, Archive etc.)
        Fields access (Invisible, Readonly fields for any model/app)
        Menu access(Hide any menu/submenu for any model/app for selected users)
        Views Access (Hide any view such as Tree view, Form view, Kanban view, Calendar view, Pivot & Graph view, etc)
        Or, make any user Readonly
        Also the app allows you to create user-wise access management so that you can add/remove users to and from any group(s) in batch and with much ease.

    """,
    "images": ["static/description/banner.gif"],
    "price": "199.99",
    "currency": "USD",
    'data':[
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        'data/view_data.xml',
        'views/access_management_view.xml',
        'views/assets.xml',
        'views/res_users_view.xml',
    ],
    'post_init_hook': 'post_install_action_dup_hook',
    'application': True,
    'installable': True,
    'auto_install': False,
}
