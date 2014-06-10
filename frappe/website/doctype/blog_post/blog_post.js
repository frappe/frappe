// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

cur_frm.cscript.refresh = function(doc) {
	if(!doc.__islocal && doc.published) {
		if(!doc.email_sent) {
			cur_frm.add_custom_button('Email Subscribers', function() {
				$c_obj(doc, 'send_emails', '', function(r) {
					cur_frm.refresh();
				});
			});
		}

		if (!doc.__islocal && doc.published) {
			cur_frm.set_intro(__("Published on website at: {0}",
				[repl('<a href="/%(website_route)s" target="_blank">/%(website_route)s</a>', doc.__onload)]));
		}
	}
}
