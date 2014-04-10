frappe.provide("frappe.core")

frappe.core.Workflow = frappe.ui.form.Controller.extend({
	refresh: function(doc) {
		this.frm.set_intro("");
		if(doc.is_active) {
			this.frm.set_intro("This Workflow is active.");
		}
		this.load_document_type(doc);
	},
	document_type: function(doc) {
		this.load_document_type(doc);
	},
	load_document_type: function(doc) {
		var me = this;
		if(doc.document_type && !locals.DocType[doc.document_type]) {
			frappe.model.with_doctype(doc.document_type, function() { 
				me.update_field_options();
			});
		}
	},
	update_field_options: function() {
		var fields = $.map(frappe.get_doc("DocType", this.frm.doc.document_type).fields, function(d) {
			return frappe.model.no_value_type.indexOf(d.fieldtype)===-1 ? d.fieldname : null;
		})
		frappe.meta.get_docfield("Workflow Document State", "update_field", this.frm.doc.name).options
			= [""].concat(fields);
	}
});

cur_frm.cscript = new frappe.core.Workflow({frm:cur_frm});