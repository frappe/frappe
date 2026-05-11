// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("S3 Backup Settings", {
	refresh: function (frm) {
		frm.clear_custom_buttons();
		frm.events.take_backup(frm);
	},

	take_backup: function (frm) {
		if (frm.doc.access_key_id && frm.doc.secret_access_key) {
			frm.add_custom_button(__("Take Backup Now"), function () {
				frm.dashboard.set_headline_alert("S3 Backup Started!");
				frappe.call({
					method: "frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backup",
					callback: function (r) {
						if (!r.exc && r.message) {
							const job_id = r.message;
							frappe.msgprint({
								message: __(
									"S3 Backup has been queued. You can track the progress <a href='/app/rq-job/{0}' target='_blank'>here</a>.",
									[job_id]
								),
							});
							frm.dashboard.clear_headline();
						}
					},
				});
			});
		}
	},
});
