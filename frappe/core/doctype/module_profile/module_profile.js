// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Module Profile', {
	refresh: function(frm) {
		if (has_common(frappe.user_roles, ["Administrator", "System Manager"])) {
			if (!frm.module_editor && frm.doc.__onload && frm.doc.__onload.all_modules) {
				let module_area = $('<div style="min-height: 300px">')
					.appendTo(frm.fields_dict.module_html.wrapper);

				frm.module_editor = new frappe.ModuleEditor(frm, module_area);
			}
		}

		if (frm.module_editor) {
			frm.module_editor.refresh();
		}
	}
});
