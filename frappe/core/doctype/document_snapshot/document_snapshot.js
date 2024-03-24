// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Document Snapshot", {
	refresh(frm) {
		$(
			frappe.render_template("document_view", {
				doc: frm.doc,
				data: JSON.parse(frm.doc.data),
			})
		).appendTo(frm.fields_dict.table_html.$wrapper.empty());
	},
});
