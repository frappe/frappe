// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Module Sidebar", {
	refresh(frm) {
		if (frm.is_new()) return;

		// `standard` is read-only on the form on purpose: setting it without also writing the
		// file leaves a row that orphan removal deletes on the next migrate. These actions do
		// both, or neither.
		if (frm.doc.standard) {
			frm.add_custom_button(__("Unmark as Standard"), () => {
				frappe.confirm(
					__("Stop shipping {0} with its app? Its exported file will be removed.", [
						frm.doc.name,
					]),
					() => frm.call("unmark_as_standard").then(() => frm.reload_doc())
				);
			});
			return;
		}

		if (!frappe.boot.developer_mode) return;

		frm.add_custom_button(__("Mark as Standard"), () => {
			const generated = frm.doc.generated
				? __(
						"It was generated from the module's contents; marking it standard adopts it as authored content."
				  )
				: "";
			frappe.confirm(
				__("Write {0} into {1} so the app ships it?", [
					frm.doc.name,
					frm.doc.app || "its app",
				]) + (generated ? " " + generated : ""),
				() => frm.call("mark_as_standard").then(() => frm.reload_doc())
			);
		});
	},
});
