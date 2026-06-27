// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("AI Knowledge Source", {
	refresh(frm) {
		apply_file_restrictions(frm);

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

	source_type(frm) {
		apply_file_restrictions(frm);
	},
});

// Cap the File picker to the formats the ingest pipeline can actually extract.
// Types come from frappe.boot
function apply_file_restrictions(frm) {
	if (frm.doc.source_type !== "File") {
		return;
	}
	const types = (frappe.boot.flow_supported_file_types || []).map((ext) => `.${ext}`);
	frm.fields_dict.file.df.options = {
		restrictions: { allowed_file_types: types },
	};
}
