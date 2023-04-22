from odoo import api, fields, models, tools


class ir_actions_actions(models.Model):
    _inherit = 'ir.actions.actions'


    # @api.model
    # @tools.ormcache('frozenset(self.env.user.groups_id.ids)', 'model_name')
    # def get_bindings(self, model_name):
    #     result = super(ir_actions_actions, self).get_bindings(model_name)
    #     self.env['res.users'].clear_caches()
    #     reports = result.get('report')
    #     actions = result.get('action')
    #     for access in self.env['remove.action'].search([('access_management_id','in',self.env.user.access_management_ids.ids),('model_id.model','=',model_name)]):
    #         report_ids = access.report_action_ids.mapped('action_id').ids
    #         if reports:
    #             rep = reports[:]
    #             for report in rep:
    #                 if report.get('id') in report_ids:
    #                     reports.remove(report)
    #         action_ids = access.server_action_ids.mapped('action_id').ids
    #         if actions:
    #             act = actions[:]
    #             for action in act:
    #                 if action.get('id') in action_ids:
    #                     actions.remove(action)
    #     if actions:
    #         result.update({'action':actions})
    #     if reports:
    #         result.update({'report':reports})
    #     return result

    @api.model
    def create(self, vals):
        res = super(ir_actions_actions, self).create(vals)
        action_data_obj = self.env['action.data']
        for record in res:
            action_data_obj.create({'name':record.name,'action_id':record.id})
        return res

    def unlink(self):
        action_data_obj = self.env['action.data']
        for record in self:
            action_data_obj.search([('action_id','=',record.id)]).unlink()
        return super(ir_actions_actions, self).unlink()