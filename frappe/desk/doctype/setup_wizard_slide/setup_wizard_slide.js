// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Setup Wizard Slide', {
	refresh: function(frm) {
		frm.toggle_reqd('ref_doctype', frm.doc.slide_type!='Information');
		frm.toggle_reqd('slide_module', frm.doc.slide_type=='Information');
	},

	ref_doctype: function(frm) {
		frm.set_query('ref_doctype', function() {
			if (frm.doc.slide_type === 'Create') {
				return {
					filters: {
						'issingle': 0,
						'istable': 0
					}
				};
			} else if (frm.doc.slide_type === 'Settings') {
				return {
					filters: {
						'issingle': 1,
						'istable': 0
					}
				};
			}
		});

		//fetch mandatory fields automatically
		if (frm.doc.ref_doctype) {
			frappe.model.clear_table(frm.doc, 'slide_fields');
			let fields = frappe.meta.get_docfields(frm.doc.ref_doctype, null, {
				reqd: 1
			});
			$.each(fields, function(_i, data) {
				let row = frappe.model.add_child(frm.doc, 'Setup Wizard Slide', 'slide_fields');
				row.label = data.label;
				row.fieldtype = data.fieldtype;
				row.fieldname = data.fieldname;
				row.options = data.options;
			});
			refresh_field('slide_fields');
		}
	}
});
