# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools,_
from odoo.exceptions import Warning, ValidationError


class ir_model_access(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    @tools.ormcache_context('self._uid', 'model', 'mode', 'raise_exception', keys=('lang',))
    def check(self, model, mode='read', raise_exception=True):
        result = super(ir_model_access, self).check(model, mode, raise_exception=raise_exception)
        try:
            is_readonly = False
            # self._cr.execute("SELECT value FROM ir_config_parameter WHERE key='uninstall_check'")
            # data = self._cr.fetchone() or False
            value = True
            # if data and data[0]:
            #     value = False
            # else:
            self._cr.execute("SELECT state FROM ir_module_module WHERE name='simplify_access_management'")
            data = self._cr.fetchone() or False
            if data and data[0] != 'installed':
                value = False
            if self.env.user.id and value:
                self._cr.execute("SELECT id FROM ir_model WHERE model='"+ model+"'")
                model_id = self._cr.fetchone()[0]
                self._cr.execute("SELECT access_management_id FROM access_management_users_rel_ah WHERE user_id="+ str(self.env.user.id)) 
                access_list = []
                for data in self._cr.fetchall():
                    access_list.append(data[0])
                if access_list:
                    a = "SELECT id FROM remove_action WHERE access_management_id in " + str(tuple(access_list)) + " and model_id = " + str(model_id) + " and readonly = True"
                    if len(access_list) == 1:
                        a = a.replace(',','')
                    self._cr.execute(a)
                    a = self._cr.fetchall()
                    if a:
                        is_readonly = True
                a = "select access_management_id from access_management_users_rel_ah where user_id = " + str(self.env.user.id)
                self._cr.execute(a)
                a = self._cr.fetchall()
                if a:
                    a = "SELECT id FROM access_management WHERE id in " + str(tuple([i[0] for i in a]+[0])) + " and readonly = True"
                    self._cr.execute(a)
                    a = self._cr.fetchall()
                if bool(a) or is_readonly:
                    if mode != 'read':  
                        return False
        except:
            pass
        return result

