// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Drive', {
	refresh: function(frm) {
		if (frm.is_new()) {
			frm.dashboard.set_headline(__("To use Google Drive, enable <a href='#Form/Google Settings'>Google Settings</a>."));
		}

		if (frm.doc.enable_system_backup) {
			let sync_button = frm.add_custom_button(__("Take Backup"), function () {
				frappe.show_alert({
					indicator: "green",
					message: __("Backing up to Google Drive.")
				});
				frappe.call({
					method: "frappe.integrations.doctype.google_drive.google_drive.upload_system_backup_to_google_drive",
					args: {
						"g_drive": frm.doc.name
					},
					btn: sync_button
				}).then((r) => {
					frappe.msgprint(r.message);
				});
			});
		}

		if (!frm.doc.backup_folder_id && frm.doc.refresh_token) {
			let sync_button = frm.add_custom_button(__("Create Folder in Google Drive"), function () {
				frappe.show_alert({
					indicator: "green",
					message: __("Creating folder in Google Drive.")
				});
				frappe.call({
					method: "frappe.integrations.doctype.google_drive.google_drive.create_folder_in_google_drive",
					args: {
						"g_drive": frm.doc.name
					},
					btn: sync_button
				}).then((r) => {
					refresh_field("backup_folder_id");
					frappe.msgprint(r.message);
				});
			});
		} else {
			frm.set_df_property("backup_folder_id", "read_only", 1);
		}
	},
	authorize_google_drive_access: function(frm) {
		let reauthorize = 0;
		if(frm.doc.authorization_code) {
			reauthorize = 1;
		}

		frappe.call({
			method: "frappe.integrations.doctype.google_drive.google_drive.authorize_access",
			args: {
				"g_drive": frm.doc.name,
				"reauthorize": reauthorize
			},
			callback: function(r) {
				if(!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			}
		});
	}
});
