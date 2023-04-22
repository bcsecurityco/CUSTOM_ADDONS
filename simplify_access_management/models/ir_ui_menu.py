from odoo import fields, models, api, _

class ir_ui_menu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        ids = super(ir_ui_menu, self).search(args, offset=0, limit=None, order=order, count=False)
        user = self.env['res.users'].browse(self._uid)
        # user.clear_caches()
        for access in user.access_management_ids:
            for menu_id in access.hide_menu_ids:
                if menu_id in ids:
                    ids = ids - menu_id
        if offset:
            ids = ids[offset:]
        if limit:
            ids = ids[:limit]
        return len(ids) if count else ids


    