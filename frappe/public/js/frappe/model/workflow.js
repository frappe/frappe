// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.workflow");

frappe.workflow = {
	state_fields: {},
	workflows: {},
	get_workflow: function(doc){
		return frappe.model.get_docinfo(doc.doctype, doc.name)  && frappe.model.get_docinfo(doc.doctype, doc.name)['workflow'] ;
	},
	get_state_fieldname: function(doc) {
		return this.get_workflow(doc)  && this.get_workflow(doc)['workflow_state_field'];
	},
	get_default_state: function(doc, docstatus) {		
		var value = null;
		$.each(this.get_workflow(doc).states, function(i, workflow_state) {
			if(cint(workflow_state.doc_status)===cint(docstatus)) {
				value = workflow_state.state;
				return false;
			}
		});
		return value;
	},
	get_transitions: function(doc) {
		return frappe.xcall('frappe.model.workflow.get_transitions', {doc: doc});
	},
	get_document_state: function(doc, state) {
		return frappe.get_children(this.get_workflow(doc), "states", {state:state})[0];
	},
	is_self_approval_enabled: function(doc) {
		return this.get_workflow(doc) && this.get_workflow(doc)['allow_self_approval'];
	},
	is_read_only: function(doc) {
		if(!doc)
			return false;
		if(doc.__islocal)
			return false;
		var state_fieldname = this.get_state_fieldname(doc);
		if(state_fieldname) {
			//var doc = locals[doctype][name];
			var state = doc[state_fieldname] || this.get_default_state(doc, doc.docstatus);
			var filters={'status':['!=','Completed'],'reference_doctype':doc.doctype,'reference_name':doc.name,'user':frappe.session.user}
			return frappe.db.get_value('Workflow Action',filters,'user').then((r) => {
				var allow_edit = state ? this.get_document_state(doc, state) && this.get_document_state(doc, state).allow_edit : null;			
				if((!frappe.user_roles.includes(allow_edit)) || (!r.message)) {
					return true;
				}	
			})			
		}
		return false;
	},
	get_update_fields: function(doc) {
		var update_fields = $.unique($.map(this.get_workflow(doc)['states'] || [],
			function(d) {
				return d.update_field;
			}));
		return update_fields;
	},
	get_state(doc) {
		const state_field = this.get_state_fieldname(doc);
		let state = doc[state_field];
		if (!state) {
			state = this.get_default_state(doc, doc.docstatus);
		}
		return state;
	},
	get_all_transitions(doc) {
		return this.get_workflow(doc).transitions || [];
	},
	get_all_transition_actions(doc) {
		const transitions = this.get_all_transitions(doc);
		return transitions.map(transition => {
			return transition.action;
		});
	},
};
