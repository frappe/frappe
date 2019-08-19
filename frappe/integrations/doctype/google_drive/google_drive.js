// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Drive', {
	refresh: function(frm) {
		if (!frm.doc.enable) {
			frm.dashboard.set_headline(__("To use Google Drive, enable <a href='#Form/Google Settings'>Google Settings</a>."));
		}

		frappe.realtime.on("upload_to_google_drive", (data) => {
			if (data.progress) {
				frm.dashboard.show_progress("Uploading to Google Drive", data.progress / data.total * 100,
					__("{0}", [data.message]));
				if (data.progress === data.total) {
					frm.dashboard.hide_progress("Uploading to Google Drive");
				}
			}
		});

		if (!frm.doc.backup_folder_id) {
			let create_button = frm.add_custom_button(__("Create Folder"), function () {
				frappe.show_alert({
					indicator: "green",
					message: __("Creating folder in Google Drive.")
				});
				frappe.call({
					method: "frappe.integrations.doctype.google_drive.google_drive.create_folder_in_google_drive",
					btn: create_button
				}).then((r) => {
					refresh_field(frm.doc.backup_folder_id);
					frappe.msgprint(r.message);
				});
			});
		}

		if (frm.doc.refresh_token && frm.doc.backup_folder_id) {
			let sync_button = frm.add_custom_button(__("Take Backup"), function () {
				frappe.show_alert({
					indicator: "green",
					message: __("Backing up to Google Drive.")
				});
				frappe.call({
					method: "frappe.integrations.doctype.google_drive.google_drive.upload_system_backup_to_google_drive",
					btn: sync_button
				}).then((r) => {
					frappe.msgprint(r.message);
				});
			});
		}
	},
	authorize_google_drive_access: function(frm) {
		let reauthorize = 0;
		if (frm.doc.authorization_code) {
			reauthorize = 1;
		}

		frappe.call({
			method: "frappe.integrations.doctype.google_drive.google_drive.authorize_access",
			args: {
				"reauthorize": reauthorize
			},
			callback: function(r) {
				if (!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			}
		});
	}
});
