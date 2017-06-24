// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
/* globals erpnext */

cur_frm.cscript.refresh = function(doc) {
	if(window.erpnext) erpnext.toggle_naming_series();
	if(!doc.__islocal && !cint(doc.email_sent) && !doc.__unsaved
			&& in_list(frappe.boot.user.can_write, doc.doctype)) {
		cur_frm.add_custom_button(__('Send'), function() {
			return $c_obj(doc, 'send_emails', '', function(r) {
				cur_frm.refresh();
			});
		}, "fa fa-play", "btn-success");
	}

	cur_frm.cscript.setup_dashboard();

	if(doc.__islocal && !doc.send_from) {
		cur_frm.set_value("send_from",
			repl("%(fullname)s <%(email)s>", frappe.user_info(doc.owner)));
	}
}

cur_frm.cscript.setup_dashboard = function() {
	if(!cur_frm.doc.__islocal && cint(cur_frm.doc.email_sent)
		&& cur_frm.doc.__onload && cur_frm.doc.__onload.status_count) {
		var stat = cur_frm.doc.__onload.status_count;
		var total = cur_frm.doc.scheduled_to_send;
		if(total) {
			$.each(stat, function(k, v) {
				stat[k] = flt(v * 100 / total, 2) + '%';
			});

			cur_frm.dashboard.add_progress("Status", [
				{
					title: stat["Not Sent"] + " Queued",
					width: stat["Not Sent"],
					progress_class: "progress-bar-info"
				},
				{
					title: stat["Sent"] + " Sent",
					width: stat["Sent"],
					progress_class: "progress-bar-success"
				},
				{
					title: stat["Sending"] + " Sending",
					width: stat["Sending"],
					progress_class: "progress-bar-warning"
				},
				{
					title: stat["Error"] + "% Error",
					width: stat["Error"],
					progress_class: "progress-bar-danger"
				}
			]);
		}
	}
}