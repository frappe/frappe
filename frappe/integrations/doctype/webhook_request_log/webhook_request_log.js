// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Webhook Request Log", {
	refresh(frm) {
		if (
			["Failed", "Exhausted"].includes(frm.doc.status) &&
			frappe.model.can_write("Webhook")
		) {
			frm.add_custom_button(__("Retry"), () => {
				frappe
					.xcall("run_doc_method", {
						dt: frm.doc.doctype,
						dn: frm.doc.name,
						method: "retry",
					})
					.then(() =>
						frappe.show_alert({
							message: __("Retry queued. Reload to see the result."),
							indicator: "green",
						})
					);
			});
		}
	},
});
