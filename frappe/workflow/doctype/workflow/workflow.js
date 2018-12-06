frappe.provide("frappe.core")

frappe.core.Workflow = Class.extend({
	init: function(args){
		$.extend(this, args);
	},
	onload: function() {
		this.frm.set_query("document_type", {"issingle": 0, "istable": 0});
	},
	refresh: function(doc) {
		this.update_field_options(doc);
	},
	document_type: function(doc) {
		this.update_field_options(doc);
	},
	update_field_options: function(doc) {
		if (doc.document_type) {
			const get_field_method = 'frappe.workflow.doctype.workflow.workflow.get_fieldnames_for';
			frappe.xcall(get_field_method, { doctype: doc.document_type })
				.then(resp => {
					frappe.meta.get_docfield("Workflow Document State", "update_field", doc.name).options = [""].concat(resp);
				})
		}
	},
	email_based_on: function(doc, cdt, cdn){
		var c_doc = frappe.get_doc(cdt, cdn);
		if(c_doc.email_based_on==="Value"){
			const get_field_method = 'frappe.workflow.doctype.workflow.workflow.get_email_fieldnames';
			frappe.xcall(get_field_method, { doctype: doc.document_type })
				.then(resp => {
					frappe.meta.get_docfield("Workflow Transition", "docfield_name", doc.name).options = [""].concat(resp);
				});
		}
	}
});

cur_frm.script_manager.make(frappe.core.Workflow);
