
from odoo.addons.web.controllers import main
from odoo.tools.translate import _
from odoo.http import request
from odoo.exceptions import UserError
from odoo import http

class Action(main.Action):
    @http.route('/web/action/load', type='json', auth="user")
    def load(self, action_id, additional_context=None):
        res = super(Action,self).load(action_id, additional_context=additional_context)
        for access in request.env['remove.action'].search([('access_management_id','in',request.env.user.access_management_ids.ids),('model_id.model','=',res.get('res_model'))]):
            for view_data in access.view_data_ids:
                for views_data_list in res.get('views'):
                    if view_data.techname == views_data_list[1]:
                        res['views'].pop(res['views'].index(views_data_list))       
        if 'views' in res.keys() and not len(res.get('views')):
           raise UserError(_("You don't have the permission to access any views. Please contact to administrator."))
        return res
