frappe.provide("frappe.core")

frappe.ui.form.on("Workflow", {
	onload: function(frm) {
		frm.set_query("document_type", {"issingle": 0, "istable": 0});
	},
	refresh: function(frm) {
		frm.events.update_field_options(frm);
	},
	document_type: function(frm) {
		frm.events.update_field_options(frm);
	},
	update_field_options: function(frm) {
		var doc = frm.doc;
		if(doc.document_type) {
			frappe.model.with_doctype(doc.document_type, function() {
				var fields = $.map(frappe.get_doc("DocType",
					frm.doc.document_type).fields, function(d) {
					return frappe.model.no_value_type.indexOf(d.fieldtype)===-1 ? d.fieldname : null;
				})
				frappe.meta.get_docfield("Workflow Document State", "update_field", frm.doc.name).options
					= [""].concat(fields);
			});
		}
	}
})

