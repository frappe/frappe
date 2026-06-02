// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("AI Model", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Test Connection"), async () => {
			if (frm.is_dirty()) {
				frappe.msgprint({
					title: __("Unsaved Changes"),
					message: __("Save the document before testing the connection."),
					indicator: "orange",
				});
				return;
			}

			frappe.dom.freeze(__("Testing connection…"));
			try {
				const r = await frm.call("test_connection");
				if (r && r.message && r.message.ok) {
					frappe.show_alert({
						message: r.message.message || __("Connection OK"),
						indicator: "green",
					});
				}
			} finally {
				frappe.dom.unfreeze();
			}
		});
	},
});
