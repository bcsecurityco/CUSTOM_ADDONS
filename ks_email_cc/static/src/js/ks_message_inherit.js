odoo.define('ks_email_cc/static/src/js/message_inherit.js', function (require) {
    'use strict';

    const {
        registerClassPatchModel,
        registerFieldPatchModel,
    } = require('mail/static/src/model/model_core.js');
    const { attr } = require('mail/static/src/model/model_field.js');

    registerFieldPatchModel('mail.message', 'ks_email_cc/static/src/js/message_inherit.js', {
        ks_cc_partners: attr({
            default: false,
        }),
        ks_bcc_partners: attr({
            default: false,
        }),
        ks_email_cc_string: attr({
            default: false,
        }),
        ks_email_bcc_string: attr({
            default: false,
        }),
    });
    registerClassPatchModel('mail.message', 'ks_email_cc/static/src/js/message_inherit.js', {
        //----------------------------------------------------------------------
        // Public
        //----------------------------------------------------------------------

        /**
         * @override
         */
        convertData(data) {
            const data2 = this._super(data);
            if (Object.keys(data).includes('ks_cc_partners') && data.ks_cc_partners) {
                if (!data2.ks_cc_partners) {
                    data2.ks_cc_partners = data.ks_cc_partners;
                }
            }
            if (Object.keys(data).includes('ks_bcc_partners') && data.ks_bcc_partners) {
                if (!data2.ks_bcc_partners) {
                    data2.ks_bcc_partners = data.ks_bcc_partners;
                }
            }
            if (Object.keys(data).includes('ks_email_cc_string') && data.ks_email_cc_string) {
                if (!data2.ks_email_cc_string) {
                    data2.ks_email_cc_string = data.ks_email_cc_string
                }
            }
            if (Object.keys(data).includes('ks_email_bcc_string') && data.ks_email_bcc_string) {
                if (!data2.ks_email_bcc_string) {
                    data2.ks_email_bcc_string = data.ks_email_bcc_string
                }
            }
            return data2;
        },
    });
});
