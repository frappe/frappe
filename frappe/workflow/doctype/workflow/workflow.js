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
		if (doc.document_type) {
			const get_field_method = 'frappe.workflow.doctype.workflow.workflow.get_fieldnames_for';
			frappe.xcall(get_field_method, { doctype: doc.document_type })
				.then(resp => {
					frappe.meta.get_docfield("Workflow Document State", "update_field", frm.doc.name).options = [""].concat(resp);
				})
		}
	}
})

frappe.ui.form.on("Workflow Transition", {

	"email_based_on": function(frm, cdt, cdn){
		var c_doc = frappe.get_doc(cdt, cdn);
		var doc = frm.doc;
		if(c_doc.email_based_on==="DocField"){
			const get_field_method = 'frappe.workflow.doctype.workflow.workflow.get_email_fieldnames';
			frappe.xcall(get_field_method, { doctype: doc.document_type })
				.then(resp => {
					frappe.meta.get_docfield("Workflow Transition", "docfield_name", frm.doc.name).options = [""].concat(resp);
				});
		}
	}
});
