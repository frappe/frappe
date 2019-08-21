// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on('Property Setter', {
	validate: function(frm) {
		if(frm.doc.property_type=='Check' && !in_list(['0','1'], frm.doc.value)) {
			frappe.throw(__('Value for a check field can be either 0 or 1'));
		}
	},
	onload: function(frm) {
		frm.set_query("doc_type", function() {
			return {
				translate_values: false,
				filters: [
					['DocType', 'issingle', '=', 0],
					['DocType', 'custom', '=', 0],
					['DocType', 'name', 'not in', frappe.model.core_doctypes_list],
					['DocType', 'restrict_to_domain', 'in', frappe.boot.active_domains]
				]
			};
		});
	}
});
