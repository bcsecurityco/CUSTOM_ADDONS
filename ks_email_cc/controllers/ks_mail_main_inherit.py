from odoo.addons.mail.controllers.main import MailController
from odoo import http,_
from odoo.http import request


class MailControllerInherit(MailController):
    @http.route('/mail/get_suggested_recipients', type='json', auth='user')
    def message_get_suggested_recipients(self, model, res_ids):
        """
            We have overrided this controller in order to add all the followers for selection on frontend
            :return: Reciepents Lists
        """
        res = super(MailControllerInherit, self).message_get_suggested_recipients(model, res_ids)
        records = request.env[model].browse(res_ids)
        for x in records.message_follower_ids.partner_id:
            records._message_add_suggested_recipient(res, partner=x, reason=_('Customer'))
        return res