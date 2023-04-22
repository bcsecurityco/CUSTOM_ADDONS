from odoo import models, SUPERUSER_ID


class ir_ui_view(models.Model):
    _inherit = 'ir.ui.view'

    def _apply_groups(self, node, name_manager, node_info):
        
        try:
            # if self.type == 'kanban':
            #     # print('a')
            hide_field_obj = self.env['hide.field'].sudo()
            for hide_field in hide_field_obj.search([('model_id.model','=',name_manager.Model._name),('access_management_id.user_ids','in',self._uid)]):
                for field_id in hide_field.field_id:
                    if (node.tag == 'field' and node.get('name') == field_id.name):
                        if hide_field.invisible:
                            node_info['modifiers']['invisible'] = hide_field.invisible
                            node.set('invisible', '1')
                        if hide_field.readonly:
                            node_info['modifiers']['readonly'] = hide_field.readonly
                            node.set('readonly', '1')
            if node.get('groups'):
                can_see = self.user_has_groups(groups=node.get('groups'))
                if not can_see:
                    node.set('invisible', '1')
                    node_info['modifiers']['invisible'] = True
                    if 'attrs' in node.attrib:
                        del node.attrib['attrs']    # avoid making field visible later
            del node.attrib['groups']
        except Exception:
            pass
        #     return True
        # return True
