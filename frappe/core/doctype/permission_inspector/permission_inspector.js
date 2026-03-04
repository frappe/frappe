// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

const call_debug = (frm) => {
	frm.trigger("debug");
};

frappe.ui.form.on("Permission Inspector", {
	refresh(frm) {
		frm.disable_save();
	},
	docname: call_debug,
	ref_doctype(frm) {
		frm.doc.docname = ""; // Usually doctype change invalidates docname
		call_debug(frm);
		frm.trigger("add_custom_perm_types");
	},
	user: call_debug,
	permission_type: call_debug,
	debug(frm) {
		if (frm.doc.ref_doctype && frm.doc.user) {
			frm.call("debug");
		}
	},
	add_custom_perm_types(frm) {
		if (!frm.doc.ref_doctype) return;

		const doctype_ptype_map = frm.doc.__onload.doctype_ptype_map;
		if (!Object.keys(doctype_ptype_map).length) return;

		const standard_options = frm.meta.fields.find(
			(f) => f.fieldname === "permission_type"
		).options;
		const custom_options = doctype_ptype_map[frm.doc.ref_doctype]?.join("\n");

		frm.set_df_property(
			"permission_type",
			"options",
			`${standard_options}\n${custom_options}`
		);
	},
});
