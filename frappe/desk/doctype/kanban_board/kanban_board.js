// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Kanban Board', {
	onload: function(frm) {
		frm.trigger('reference_doctype');
	},
	refresh: function(frm) {
		if(frm.is_new()) return;
		frm.add_custom_button("Show Board", function() {
			frappe.set_route("List", frm.doc.reference_doctype, "Kanban", frm.doc.name);
		});
	},
	reference_doctype: function(frm) {

		// set field options
		if(!frm.doc.reference_doctype) return;

		frappe.model.with_doctype(frm.doc.reference_doctype, function() {
			var options = $.map(frappe.get_meta(frm.doc.reference_doctype).fields,
				function(d) {
					if(d.fieldname && d.fieldtype === 'Select' &&
						frappe.model.no_value_type.indexOf(d.fieldtype)===-1) {
						return d.fieldname;
					}
					return null;
				});
			frm.set_df_property('field_name', 'options', options);
			frm.get_field('field_name').refresh();
		});
	},
	field_name: function(frm) {
		var field = frappe.meta.get_field(frm.doc.reference_doctype, frm.doc.field_name);
		frm.doc.columns = [];
		field.options && field.options.split('\n').forEach(function(o) {
			o = o.trim();
			if(!o) return;
			var d = frm.add_child('columns');
			d.column_name = o;
		});
		frm.refresh();
	}
});
