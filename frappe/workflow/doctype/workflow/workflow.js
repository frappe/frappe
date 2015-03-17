frappe.provide("frappe.core")

frappe.core.Workflow = frappe.ui.form.Controller.extend({
	refresh: function(doc) {
		this.update_field_options(doc);
	},
	document_type: function(doc) {
		this.update_field_options(doc);
	},
	update_field_options: function(doc) {
		var me = this;
		if(doc.document_type) {
			frappe.model.with_doctype(doc.document_type, function() {
				var fields = $.map(frappe.get_doc("DocType",
					me.frm.doc.document_type).fields, function(d) {
					return frappe.model.no_value_type.indexOf(d.fieldtype)===-1 ? d.fieldname : null;
				})
				frappe.meta.get_docfield("Workflow Document State", "update_field", me.frm.doc.name).options
					= [""].concat(fields);
			});
		}
	}
});

cur_frm.cscript = new frappe.core.Workflow({frm:cur_frm});
