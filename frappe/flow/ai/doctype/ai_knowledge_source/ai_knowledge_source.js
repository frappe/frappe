// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("AI Knowledge Source", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Resync"), async () => {
			await frm.call("resync");
			frappe.show_alert({ message: __("Resync started"), indicator: "blue" });
			frm.reload_doc();
		});

		if (frm.doc.source_type === "DocType") {
			frm.add_custom_button(__("Reconcile"), async () => {
				await frm.call("reconcile");
				frappe.show_alert({ message: __("Reconcile started"), indicator: "blue" });
			});
		}
	},
});
