from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from bs4 import BeautifulSoup
from lxml import etree


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def load_views(self, views, options=None):
        actions_and_prints = []
        for access in self.env['remove.action'].search([('access_management_id','in',self.env.user.access_management_ids.ids),('model_id.model','=',self._name)]):
            actions_and_prints = actions_and_prints + access.mapped('report_action_ids.action_id').ids
            actions_and_prints = actions_and_prints + access.mapped('server_action_ids.action_id').ids
            for view_data in access.view_data_ids:
                for view_data_list in views:
                    if view_data.techname == view_data_list[1]:
                        views.pop(views.index(view_data_list))
        
        res = super(BaseModel, self).load_views(views, options=options)      

        if 'fields_views' in res.keys():
            for view in ['list','form']:
                if view in res['fields_views'].keys():
                    if 'toolbar' in res['fields_views'][view].keys():
                        if 'print' in res['fields_views'][view]['toolbar'].keys():
                            prints = res['fields_views'][view]['toolbar']['print'][:]
                            for pri in prints:
                                if pri['id'] in actions_and_prints:
                                    res['fields_views'][view]['toolbar']['print'].remove(pri)
                        if 'print' in res['fields_views'][view]['toolbar'].keys():
                            action = res['fields_views'][view]['toolbar']['action'][:]
                            for act in action:
                                if act['id'] in actions_and_prints:
                                    res['fields_views'][view]['toolbar']['action'].remove(act)
        return res
    
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id, view_type, toolbar, submenu)

        access_recs = self.env['remove.action'].search([('access_management_id.user_ids','in',self.env.user.id),('model_id.model','=',res['model'])])
        delete = False
        edit = False
        create = False
        readonly = False
        for access_rec in access_recs:
            if access_rec.restrict_create:
                create = True
            if access_rec.restrict_edit:
                edit = True
            if access_rec.restrict_delete:
                delete = True
        if not readonly:
            
            if view_type == 'form':
                write = False
                doc = etree.XML(res['arch'])
                if create:
                    write = True
                    doc.attrib.update({'create':'false'})
                if delete:
                    write = True
                    doc.attrib.update({'delete':'false'})
                if edit:
                    write = True
                    doc.attrib.update({'edit':'false'})
                if write:
                    res['arch'] = etree.tostring(doc, encoding='unicode')
            if view_type == 'tree':
                write = False
                doc = etree.XML(res['arch'])
                if create:
                    write = True
                    doc.attrib.update({'create':'false'})
                if delete:
                    write = True
                    doc.attrib.update({'delete':'false'})
                if edit:
                    write = True
                    doc.attrib.update({'edit':'false'})
                if write:
                    res['arch'] = etree.tostring(doc, encoding='unicode')
            if view_type == 'kanban':
                write = False
                doc = etree.XML(res['arch'])
                if create:
                    doc.attrib.update({'create':'false'})
                    write = True
                if delete:
                    doc.attrib.update({'delete':'false'})
                    write = True
                if edit:
                    doc.attrib.update({'edit':'false'})
                    write = True
                for hide in self.env['hide.field'].search([('model_id.model','=',self._name),('access_management_id.user_ids','in',self._uid)]):
                    for field_id in hide.field_id:
                        for tag in doc.xpath("//t[@t-esc='record." + field_id.name + ".value']"):
                            # tag.attrib.update({'invisible':'1','modifiers':"{&quot;invisible&quot;:true}"})
                            if hide.invisible:
                                tag.set('invisible','1')
                                tag.set('modifiers',"{&quot;invisible&quot;:true}")
                                write = True
                            # if hide.readonly:
                            #     tag.set('readonly','1')
                            #     tag.set('modifiers',"{&quot;readonly&quot;:true}")
                            #     write = True
                        for tag in doc.xpath("//field[@name='" + field_id.name + "']"):
                            if hide.invisible:
                                tag.set('invisible','1')
                                tag.set('modifiers',"{&quot;invisible&quot;:true}")
                                write = True
                            # if hide.readonly:
                            #     tag.set('readonly','1')
                            #     tag.set('modifiers',"{&quot;readonly&quot;:true}")
                            #     write = True
                if write:
                    res['arch'] = etree.tostring(doc, encoding='unicode').replace('&amp;quot;','&quot;')
            
        return res
