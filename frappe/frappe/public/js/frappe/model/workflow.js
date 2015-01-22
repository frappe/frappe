// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

frappe.provide("frappe.workflow");

frappe.workflow = {
	state_fields: {},
	workflows: {},
	setup: function(doctype) {
		var wf = frappe.get_list("Workflow", {document_type: doctype});
		if(wf.length) {
			frappe.workflow.workflows[doctype] = wf[0];
			frappe.workflow.state_fields[doctype] = wf[0].workflow_state_field;
		} else {
			frappe.workflow.state_fields[doctype] = null;
		}		
	},
	get_state_fieldname: function(doctype) {
		if(frappe.workflow.state_fields[doctype]===undefined) {
			frappe.workflow.setup(doctype);
		}
		return frappe.workflow.state_fields[doctype];
	},
	get_default_state: function(doctype) {
		frappe.workflow.setup(doctype);
		return frappe.workflow.workflows[doctype].workflow_document_states[0].state;
	},
	get_transitions: function(doctype, state) {
		frappe.workflow.setup(doctype);
		return frappe.get_children(frappe.workflow.workflows[doctype], "workflow_transitions", {state:state});
	},
	get_document_state: function(doctype, state) {
		frappe.workflow.setup(doctype);
		return frappe.get_children(frappe.workflow.workflows[doctype], "workflow_document_states", {state:state})[0];
	},
	get_next_state: function(doctype, state, action) {
		return frappe.get_children(frappe.workflow.workflows[doctype], "workflow_transitions", {
			state:state, action:action})[0].next_state;
	},
 	is_read_only: function(doctype, name) {
		var state_fieldname = frappe.workflow.get_state_fieldname(doctype);
		if(state_fieldname) {
			if(!locals[doctype][name])
				return false;
			if(locals[doctype][name].__islocal)
				return false;
				
			var state = locals[doctype][name][state_fieldname] || 
				frappe.workflow.get_default_state(doctype);

			var allow_edit = state ? frappe.workflow.get_document_state(doctype, state).allow_edit : null;

			if(user_roles.indexOf(allow_edit)==-1) {
				return true;
			}
		}
		return false;
	},
	get_update_fields: function(doctype) {
		var update_fields = $.unique($.map(frappe.workflow.workflows[doctype].workflow_document_states || [], 
			function(d) {
				return d.update_field;
			}));
		return update_fields;
	}
};