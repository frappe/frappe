// Copyright (c) 2016, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Dropbox Settings", {
	refresh: function (frm) {
		frm.toggle_display(
			["app_access_key", "app_secret_key"],
			!frm.doc.__onload?.dropbox_setup_via_site_config
		);
		frm.events.take_backup(frm);
	},

	are_keys_present: function (frm) {
		return (
			(frm.doc.app_access_key && frm.doc.app_secret_key) ||
			frm.doc.__onload?.dropbox_setup_via_site_config
		);
	},

	allow_dropbox_access: function (frm) {
		if (!frm.events.are_keys_present(frm)) {
			nts.msgprint(__("App Access Key and/or Secret Key are not present."));
			return;
		}

		nts.call({
			method: "nts.integrations.doctype.dropbox_settings.dropbox_settings.get_dropbox_authorize_url",
			freeze: true,
			callback: function (r) {
				if (!r.exc) {
					window.open(r.message.auth_url);
				}
			},
		});
	},

	take_backup: function (frm) {
		if (frm.doc.enabled && (frm.doc.dropbox_refresh_token || frm.doc.dropbox_access_token)) {
			frm.add_custom_button(__("Take Backup Now"), function () {
				nts.call({
					method: "nts.integrations.doctype.dropbox_settings.dropbox_settings.take_backup",
					freeze: true,
				});
			});
		}
	},
});
