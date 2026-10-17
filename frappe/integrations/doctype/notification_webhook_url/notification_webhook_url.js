// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Notification Webhook URL", {
	refresh(frm) {
		if (!frm.is_new() && frappe.user_roles.includes("System Manager")) {
			frm.add_custom_button(__("Send Test Message"), () => frm.trigger("show_send_dialog"));
		}
	},

	show_send_dialog(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Send Test Message"),
			fields: [
				{
					fieldtype: "Small Text",
					label: __("Message"),
					fieldname: "message",
					default: __("Test message"),
					reqd: 1,
				},
				{
					fieldtype: "Link",
					options: "DocType",
					label: __("Reference DocType"),
					fieldname: "reference_doctype",
					default: frm.doc.doctype,
					reqd: 1,
				},
				{
					fieldtype: "Dynamic Link",
					options: "reference_doctype",
					label: __("Reference Name"),
					fieldname: "reference_name",
					default: frm.doc.name,
					reqd: 1,
				},
			],
			primary_action_label: __("Send"),
			async primary_action(values) {
				await frm.call("send_test_message", values);
				dialog.hide();
				frappe.show_alert({ message: __("Test message sent"), indicator: "green" });
			},
		});
		dialog.show();
	},
});
