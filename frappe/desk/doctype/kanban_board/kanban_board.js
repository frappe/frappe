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

		if(!frm.doc.reference_doctype) return;

		// set field options
		frm.trigger("set_field_options");

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
	},
	set_field_options: function(frm) {
		frappe.model.with_doctype(frm.doc.reference_doctype, function() {
			let  field_name_option = [], card_fields_option = [];
			frappe.get_meta(frm.doc.reference_doctype).fields.map(function(d) {

				if (frappe.model.no_value_type.indexOf(d.fieldtype) === -1) {			
					card_fields_option.push({ label: d.label + ' (' + d.fieldtype + ')', value: d.fieldname });

					if (d.fieldtype === 'Select') {
						field_name_option.push(d.fieldname);
					}
				}
			});
			frappe.meta.get_docfield("Kanban Board Card Field", "field_name", frm.doc.name).options = [""].concat(card_fields_option);
			frm.set_df_property('field_name', 'options', field_name_option);
		});
	}
});

frappe.ui.form.on("Kanban Board Card Field", {
	field_name: function(frm, cdt, cdn) {
		let doc = frappe.get_doc(cdt, cdn);
		
		let df = frappe.get_meta(frm.doc.reference_doctype).fields.filter(function (d) {
			return d.fieldname == doc.field_name;
		})[0];
		
		doc.label = df.label;
		frm.refresh_field("card_fields");
	}
});
