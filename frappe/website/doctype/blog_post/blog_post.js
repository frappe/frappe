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

		cur_frm.appframe.add_button("View In Website", function() {
			window.open(doc.__onload.website_route);
		}, "icon-globe");
	}
}
