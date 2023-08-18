// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Document Comparator", {
	refresh(frm) {
		frm.page.clear_indicator();

		frm.disable_save();

		frm.set_query("doctype_name", () => {
			return {
				filters: {
					track_changes: 1,
				},
			};
		});

		frm.page.set_primary_action("Compare", () => {
			frm.call({
				doc: frm.doc,
				method: "compare_document",
				callback: function (r) {
					let document_names = r.message[0];
					let changed_fields = r.message[1];
					let render_dict = {
						documents: document_names,
						changed: changed_fields.changed,
						row_changed: changed_fields.row_changed,
					};
					$(frappe.render_template("document_comparator", render_dict)).appendTo(
						frm.fields_dict.version_table.$wrapper.empty()
					);
				},
			});
		});
	},
});
