frappe.ui.form.on("Email Domain", {
	onload: function (frm) {
		if (!frm.doc.__islocal) {
			frm.dashboard.clear_headline();
			let msg = __(
				"Changing any setting will reflect on all the email accounts associated with this domain."
			);
			frm.dashboard.set_headline_alert(msg);
		} else {
			if (!frm.doc.attachment_limit) {
				frappe.call({
					method: "frappe.core.api.file.get_max_file_size",
					callback: function (r) {
						if (!r.exc) {
							frm.set_value("attachment_limit", Number(r.message) / (1024 * 1024));
						}
					},
				});
			}
		}
	},
});
