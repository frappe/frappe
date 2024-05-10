// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Google Contacts", {
	refresh: function (frm) {
		if (!frm.doc.enable) {
			frm.dashboard.set_headline(
				__("To use Google Contacts, enable {0}.", [
					`<a href='/app/google-settings'>${__("Google Settings")}</a>`,
				])
			);
		}

		frappe.realtime.on("import_google_contacts", (data) => {
			if (data.progress) {
				frm.dashboard.show_progress(
					"Import Google Contacts",
					(data.progress / data.total) * 100,
					__("Importing {0} of {1}", [data.progress, data.total])
				);
				if (data.progress === data.total) {
					frm.dashboard.hide_progress("Import Google Contacts");
				}
			}
		});

		if (frm.doc.refresh_token) {
			let sync_button = frm.add_custom_button(__("Sync Contacts"), function () {
				frappe.show_alert({
					indicator: "green",
					message: __("Syncing"),
				});
				frappe
					.call({
						method: "frappe.integrations.doctype.google_contacts.google_contacts.sync",
						args: {
							g_contact: frm.doc.name,
						},
						btn: sync_button,
					})
					.then((r) => {
						frappe.hide_progress();
						frappe.msgprint(r.message);
					});
			});
		}
	},
	authorize_google_contacts_access: function (frm) {
		frappe.call({
			method: "frappe.integrations.doctype.google_contacts.google_contacts.authorize_access",
			args: {
				g_contact: frm.doc.name,
				reauthorize: frm.doc.authorization_code ? 1 : 0,
			},
			callback: function (r) {
				if (!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			},
		});
	},
});
