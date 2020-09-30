// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Web Template', {
	refresh: function(frm) {
		if (!frappe.boot.developer_mode && frm.doc.standard) {
			frm.disable_form();
		}

		frm.toggle_display('standard', frappe.boot.developer_mode);
		frm.toggle_display('template', !frm.doc.standard);
	},
	standard: function(frm) {
		if (!frm.doc.standard) {
			// If standard changes from true to false, hide template until
			// the next save. Changes will get overwritten from the backend
			// on save and should not be possible in the UI.
			frm.toggle_display('template', false);
			frm.save();
		}
	}
});
