// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

const call_debug = (frm) => {
	frm.trigger("debug");
};

frappe.ui.form.on("Permission Debugger", {
	refresh(frm) {
		frm.disable_save();
	},
	docname: call_debug,
	ref_doctype: call_debug,
	user: call_debug,
	permission_type: call_debug,
	debug(frm) {
		if (frm.doc.docname && frm.doc.ref_doctype && frm.doc.user) {
			frm.call("debug");
		}
	},
});
