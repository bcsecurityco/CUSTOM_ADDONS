from odoo import _, api, exceptions, fields, models, tools, registry, SUPERUSER_ID
from odoo.http import _logger
import threading
from odoo.tools.misc import clean_context, split_every


class MailThreadInherit(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread(self, message, msg_vals=False, notify_by_email=True, **kwargs):
        """ Main notification method. This method basically does two things

         * call ``_notify_compute_recipients`` that computes recipients to
           notify based on message record or message creation values if given
           (to optimize performance if we already have data computed);
         * performs the notification process by calling the various notification
           methods implemented;

        This method cnn be overridden to intercept and postpone notification
        mechanism like mail.channel moderation.

        :param message: mail.message record to notify;
        :param msg_vals: dictionary of values used to create the message. If given
          it is used instead of accessing ``self`` to lessen query count in some
          simple cases where no notification is actually required;

        Kwargs allow to pass various parameters that are given to sub notification
        methods. See those methods for more details about the additional parameters.
        Parameters used for email-style notifications
        """
        msg_vals = msg_vals if msg_vals else {}
        # rdata = self._no  tify_compute_recipients(message, msg_vals)
        rdata = self._notify_compute_recipients(message, msg_vals)
        if not rdata:
            return False
        elif self.env.context.get('ks_from_button'):
            # Added custom changes here to check that if this method is called from frontend then only send to those recipients if they are selected
            rdata.update({'partners': [x for x in rdata.get('partners', []) if x['id'] in message.partner_ids.ids]})

        message_values = {}
        if rdata['channels']:
            message_values['channel_ids'] = [(6, 0, [r['id'] for r in rdata['channels']])]

        self._notify_record_by_inbox(message, rdata, msg_vals=msg_vals, **kwargs)
        if notify_by_email:
            self._notify_record_by_email(message, rdata, msg_vals=msg_vals, **kwargs)

        return rdata

    def _message_add_suggested_recipient(self, result, partner=None, email=None, reason=''):
        """
            Overrided this method to add all the followers in the suggested recipients list if present
        """
        res = super(MailThreadInherit, self)._message_add_suggested_recipient(result, partner, email, reason)
        if partner and partner in self.message_partner_ids:
            if partner and partner.id in [val[0] for val in result[self.ids[0]]]:  # already existing partner ID -> skip
                return result
            if partner and partner.email:  # complete profile: id, name <email>
                result[self.ids[0]].append((partner.id, partner.email_formatted, reason))
            elif partner:  # incomplete profile: id, name
                result[self.ids[0]].append((partner.id, '%s' % (partner.name), reason))
            else:  # unknown partner, we are probably managing an email address
                result[self.ids[0]].append((False, email, reason))
            return result
        else:
            return res

    def _notify_record_by_email(self, message, recipients_data, msg_vals=False,
                                model_description=False, mail_auto_delete=True, check_existing=False,
                                force_send=True, send_after_commit=True,
                                **kwargs):
        """ Method to send email linked to notified messages.

        :param message: mail.message record to notify;
        :param recipients_data: see ``_notify_thread``;
        :param msg_vals: see ``_notify_thread``;

        :param model_description: model description used in email notification process
          (computed if not given);
        :param mail_auto_delete: delete notification emails once sent;
        :param check_existing: check for existing notifications to update based on
          mailed recipient, otherwise create new notifications;

        :param force_send: send emails directly instead of using queue;
        :param send_after_commit: if force_send, tells whether to send emails after
          the transaction has been committed using a post-commit hook;
        """
        partners_data = [r for r in recipients_data['partners'] if r['notif'] == 'email']
        if not partners_data:
            return True

        model = msg_vals.get('model') if msg_vals else message.model
        model_name = model_description or (self._fallback_lang().env['ir.model']._get(
            model).display_name if model else False)  # one query for display name
        recipients_groups_data = self._notify_classify_recipients(partners_data, model_name, msg_vals=msg_vals)

        if not recipients_groups_data:
            return True
        force_send = self.env.context.get('mail_notify_force_send', force_send)

        template_values = self._notify_prepare_template_context(message, msg_vals,
                                                                model_description=model_description)  # 10 queries

        email_layout_xmlid = msg_vals.get('email_layout_xmlid') if msg_vals else message.email_layout_xmlid
        template_xmlid = email_layout_xmlid if email_layout_xmlid else 'mail.message_notification_email'
        try:
            base_template = self.env.ref(template_xmlid, raise_if_not_found=True).with_context(
                lang=template_values['lang'])  # 1 query
        except ValueError:
            _logger.warning(
                'QWeb template %s not found when sending notification emails. Sending without layouting.' % (
                    template_xmlid))
            base_template = False

        mail_subject = message.subject or (
                    message.record_name and 'Re: %s' % message.record_name)  # in cache, no queries
        # prepare notification mail values
        base_mail_values = {
            'mail_message_id': message.id,
            'mail_server_id': message.mail_server_id.id,
            # 2 query, check acces + read, may be useless, Falsy, when will it be used?
            'auto_delete': mail_auto_delete,
            # due to ir.rule, user have no right to access parent message if message is not published
            'references': message.parent_id.sudo().message_id if message.parent_id else False,
            'subject': mail_subject,
        }
        base_mail_values = self._notify_by_email_add_values(base_mail_values)

        # Clean the context to get rid of residual default_* keys that could cause issues during
        # the mail.mail creation.
        # Example: 'default_state' would refer to the default state of a previously created record
        # from another model that in turns triggers an assignation notification that ends up here.
        # This will lead to a traceback when trying to create a mail.mail with this state value that
        # doesn't exist.
        SafeMail = self.env['mail.mail'].sudo().with_context(clean_context(self._context))
        SafeNotification = self.env['mail.notification'].sudo().with_context(clean_context(self._context))
        emails = self.env['mail.mail'].sudo()

        # loop on groups (customer, portal, user,  ... + model specific like group_sale_salesman)
        notif_create_values = []
        recipients_max = 50
        for recipients_group_data in recipients_groups_data:
            # generate notification email content
            recipients_ids = recipients_group_data.pop('recipients')
            render_values = {**template_values, **recipients_group_data}
            # {company, is_discussion, lang, message, model_description, record, record_name, signature, subtype, tracking_values, website_url}
            # {actions, button_access, has_button_access, recipients}

            if base_template:
                mail_body = base_template._render(render_values, engine='ir.qweb', minimal_qcontext=True)
            else:
                mail_body = message.body
            mail_body = self.env['mail.render.mixin']._replace_local_links(mail_body)

            # create email
            for recipients_ids_chunk in split_every(recipients_max, recipients_ids):
                recipient_values = self._notify_email_recipient_values(recipients_ids_chunk)
                email_to = recipient_values['email_to']
                recipient_ids = recipient_values['recipient_ids']

                create_values = {
                    'body_html': mail_body,
                    'subject': mail_subject,
                    'recipient_ids': [(4, pid) for pid in recipient_ids],
                }
                # Added custom changes here to add the email cc and bcc from here in the mail.mail model
                if msg_vals and msg_vals.get('email_cc'):
                    create_values['email_cc'] = msg_vals.get('email_cc')
                if msg_vals and msg_vals.get('email_bcc'):
                    create_values['email_bcc'] = msg_vals.get('email_bcc')
                if email_to or (msg_vals and msg_vals.get('email_to')):
                    st = ''
                    if email_to:
                        st = email_to + ','
                    st = st + msg_vals.get('email_to')
                    if st:
                        create_values['email_to'] = st
                create_values.update(
                    base_mail_values)  # mail_message_id, mail_server_id, auto_delete, references, headers
                email = SafeMail.create(create_values)

                if email and recipient_ids:
                    tocreate_recipient_ids = list(recipient_ids)
                    if check_existing:
                        existing_notifications = self.env['mail.notification'].sudo().search([
                            ('mail_message_id', '=', message.id),
                            ('notification_type', '=', 'email'),
                            ('res_partner_id', 'in', tocreate_recipient_ids)
                        ])
                        if existing_notifications:
                            tocreate_recipient_ids = [rid for rid in recipient_ids if
                                                      rid not in existing_notifications.mapped('res_partner_id.id')]
                            existing_notifications.write({
                                'notification_status': 'ready',
                                'mail_id': email.id,
                            })
                    notif_create_values += [{
                        'mail_message_id': message.id,
                        'res_partner_id': recipient_id,
                        'notification_type': 'email',
                        'mail_id': email.id,
                        'is_read': True,  # discard Inbox notification
                        'notification_status': 'ready',
                    } for recipient_id in tocreate_recipient_ids]
                emails |= email

        if notif_create_values:
            SafeNotification.create(notif_create_values)

        # NOTE:
        #   1. for more than 50 followers, use the queue system
        #   2. do not send emails immediately if the registry is not loaded,
        #      to prevent sending email during a simple update of the database
        #      using the command-line.
        test_mode = getattr(threading.currentThread(), 'testing', False)
        if force_send and len(emails) < recipients_max and (not self.pool._init or test_mode):
            # unless asked specifically, send emails after the transaction to
            # avoid side effects due to emails being sent while the transaction fails
            if not test_mode and send_after_commit:
                email_ids = emails.ids
                dbname = self.env.cr.dbname
                _context = self._context

                @self.env.cr.postcommit.add
                def send_notifications():
                    db_registry = registry(dbname)
                    with api.Environment.manage(), db_registry.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, _context)
                        env['mail.mail'].browse(email_ids).send()
            else:
                emails.send()

        return True


class MailMessageInherit(models.Model):
    _inherit = "mail.message"
    email_cc = fields.Char('Email CC')
    email_bcc = fields.Char('Email BCC')
    email_to = fields.Char('To')
    ks_email_cc_string = fields.Char('Cc String', help='Used to store only cc mails that can be shown in chatter')
    ks_email_bcc_string = fields.Char('Bcc String', help='Used to store only bcc mails that can be shown in chatter')
    ks_cc_partners = fields.Char('cc partners string')
    ks_bcc_partners = fields.Char('bcc partners string')
    ks_cc_partner_ids = fields.Many2many('res.partner', 'mail_message_cc_partner_res_partner_rel')
    ks_bcc_partner_ids = fields.Many2many('res.partner', 'mail_message_bcc_partner_res_partner_rel')

    @api.constrains('ks_cc_partner_ids')
    def update_cc_partners_field(self):
        for rec in self:
            if rec.ks_cc_partner_ids:
                rec.ks_cc_partners = ','.join([x.name for x in rec.ks_cc_partner_ids])

    @api.constrains('ks_bcc_partner_ids')
    def update_bcc_partners_field(self):
        for rec in self:
            if rec.ks_bcc_partner_ids:
                rec.ks_bcc_partners = ','.join([x.name for x in rec.ks_bcc_partner_ids])

    def _get_message_format_fields(self):
        return [
            'id', 'body', 'date', 'author_id', 'email_from',  # base message fields
            'message_type', 'subtype_id', 'subject',  # message specific
            'model', 'res_id', 'record_name',  # document related
            'channel_ids', 'partner_ids',  # recipients
            'starred_partner_ids',  # list of partner ids for whom the message is starred
            'moderation_status', 'ks_email_cc_string', 'ks_email_bcc_string', 'ks_bcc_partners', 'ks_cc_partners'
        ]
