from odoo import fields, models, api, _
from odoo.exceptions import Warning


class access_management(models.Model):
    _name = 'access.management'
    _description = "Access Management"

    name = fields.Char('Name')
    user_ids = fields.Many2many('res.users', 'access_management_users_rel_ah', 'access_management_id', 'user_id', 'Users')

    readonly = fields.Boolean('Read-Only')

    hide_menu_ids = fields.Many2many('ir.ui.menu', 'access_management_menu_rel_ah', 'access_management_id', 'menu_id', 'Hide Menu')
    
    hide_field_ids = fields.One2many('hide.field', 'access_management_id', 'Hide Field')

    remove_action_ids = fields.One2many('remove.action', 'access_management_id', 'Remove Action')

    

    @api.model
    def create(self, vals):
        res = super(access_management, self).create(vals)
        for user in self.env['res.users'].sudo().search([('share','=',False)]):
            user.clear_caches()
        if res.readonly:
            for user in res.user_ids:
                if user.has_group('base.group_system') or user.has_group('base.group_erp_manager'):
                    raise Warning(_('Admin user can not be set as a read-only..!'))
        return res

    def unlink(self):
        res = super(access_management, self).unlink()
        for user in self.env['res.users'].sudo().search([('share','=',False)]):
            user.clear_caches()
        return res

    def write(self, vals):
        res = super(access_management, self).write(vals)
        for user in self.env['res.users'].sudo().search([('share','=',False)]):
            user.clear_caches()
        # return res
        if self.readonly:
            for user in self.user_ids:
                if user.has_group('base.group_system') or user.has_group('base.group_erp_manager'):
                    raise Warning(_('Admin user can not be set as a read-only..!'))
        users = []
        readonly_group = self.env.ref('simplify_access_management.group_read_only_ah')
        if 'user_ids' in vals.keys():
            for new_user in self.user_ids.ids:
                if new_user not in vals.get('user_ids')[0][2]:
                    users.append(new_user)
            user_list = readonly_group.users.ids
            for user_id in readonly_group.users.ids:
                if user_id in users:
                    user_list.remove(user_id)
            readonly_group.users = [(6,0,user_list)]
            users = []
            for new_user in vals.get('user_ids')[0][2]:
                if new_user not in vals.get('user_ids')[0][2]:
                    users.append(new_user)
            
            readonly_group.users = [(6,0,users+readonly_group.users.ids)]
        # res = super(access_management, self).write(vals)
        if 'readonly' in vals.keys():
            if self.readonly:
                readonly_group.users = [(6,0,list(set(readonly_group.users.ids+self.user_ids.ids)))]
            else:
                user_list = readonly_group.users.ids
                for user_id in self.user_ids.ids:
                    if user_id in user_list:
                        user_list.remove(user_id)
                readonly_group.users = [(6,0,user_list)]
        return res     


    def get_remove_options(self, model):
        remove_action = self.env['remove.action'].search([('access_management_id','in',self.env.user.access_management_ids.ids),('model_id.model','=',model)])
        options = []
        for action in remove_action:
            if action.restrict_edit:
                options.append(_('Archive'))
                options.append(_('Unarchive'))
            if action.restrict_create:
                options.append(_('Duplicate'))
            if action.restrict_export:
                options.append(_('Export'))
        return options
