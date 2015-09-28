$.extend(cur_frm.cscript, {
	onload_post_render: function() {
		cur_frm.fields_dict.allow_dropbox_access.$input.addClass("btn-primary");
	},

	refresh: function() {
		cur_frm.disable_save();
	},

	validate_send_notifications_to: function() {
		if(!cur_frm.doc.send_notifications_to) {
			msgprint(__("Please specify") + ": " +
				__(frappe.meta.get_label(cur_frm.doctype,
					"send_notifications_to")));
			return false;
		}

		return true;
	},

	allow_dropbox_access: function() {
		if(cur_frm.cscript.validate_send_notifications_to()) {
			return frappe.call({
				method: "frappe.integrations.doctype.dropbox_backup.dropbox_backup.get_dropbox_authorize_url",
				callback: function(r) {
					if(!r.exc) {
						cur_frm.set_value("dropbox_access_secret", r.message.secret);
						cur_frm.set_value("dropbox_access_key", r.message.key);
						cur_frm.save(null, function() {
							window.open(r.message.url);
						});
					}
				}
			});
		}
	}
});
