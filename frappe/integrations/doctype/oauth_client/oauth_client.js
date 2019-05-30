// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('OAuth Client', {
	refresh: (frm) => {
		frm.trigger("add_button_generate_secret");
	},

	add_button_generate_secret: (frm) => {
		frm.add_custom_button(__('Generate Secret'), () => {
			frappe.confirm(
				__("Apps using current secret won't be able to access, are you sure?"),
				() => {
					frappe.call({
						type:"POST",
						method:"frappe.integrations.doctype.oauth_client.oauth_client.generate_secret",
						args: { client_id: frm.doc.client_id },
					}).done(() => {
						frm.reload_doc();
					}).fail(() => {
						frappe.msgprint(__("Could not generate Secret"));
					});
				}
			);
		});
	},
});
