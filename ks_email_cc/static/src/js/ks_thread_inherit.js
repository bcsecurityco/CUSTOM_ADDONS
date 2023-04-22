odoo.define('ks_email_cc/static/src/js/thread_inherit.js', function (require) {
'use strict';



const {
    registerClassPatchModel,
    registerInstancePatchModel,
} = require('mail/static/src/model/model_core.js');

registerClassPatchModel('mail.thread', 'ks_email_cc/static/src/js/thread_inherit.js', {
   performRpcMessagePost({ postData, threadId, threadModel }) {
        if(Object.keys(postData).includes('subtype_xmlid') && postData['subtype_xmlid'] == 'mail.mt_comment'){
            if(Object.keys(postData).includes('context')){
                postData.context.ks_from_button = true
            } else{
                postData['context'] = {'ks_from_button': true}
            }
        }

        return this.env.services.rpc({
            model: threadModel,
            method: 'message_post',
            args: [threadId],
            kwargs: postData,
        });
    }
});
});
