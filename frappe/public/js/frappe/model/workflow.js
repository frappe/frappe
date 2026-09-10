// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.workflow");

const NUMERIC_FIELDTYPES = ["Int", "Float", "Currency", "Percent"];

function cast_condition_value(value, fieldtype) {
	if (fieldtype === "Check") return cint(value);
	if (NUMERIC_FIELDTYPES.includes(fieldtype)) return flt(value);

	return value;
}

const CONDITION_OPERATORS = {
	"=": (a, b) => a === b,
	"!=": (a, b) => a !== b,
	">": (a, b) => a > b,
	"<": (a, b) => a < b,
	">=": (a, b) => a >= b,
	"<=": (a, b) => a <= b,
};

function resolve_workflow(doc) {
	if (typeof doc === "string") {
		frappe.workflow.setup(doc);
		return frappe.workflow.workflows[doc] || null;
	}

	return frappe.workflow.get_workflow(doc);
}

frappe.workflow = {
	state_fields: {},
	workflows: {},
	candidates: {},
	avoid_status_override: {},
	setup: function (doctype) {
		const workflows = frappe
			.get_list("Workflow", { document_type: doctype })
			.sort((a, b) => cint(b.priority) - cint(a.priority));

		if (!workflows.length) {
			frappe.workflow.state_fields[doctype] = null;
			return;
		}

		frappe.workflow.candidates[doctype] = workflows;
		frappe.workflow.workflows[doctype] = workflows[0];
		frappe.workflow.state_fields[doctype] = workflows[0].workflow_state_field;
		frappe.workflow.avoid_status_override[doctype] = workflows.flatMap((workflow) =>
			(workflow.states || []).filter((row) => row.avoid_status_override).map((d) => d.state)
		);
	},
	applies_to: function (workflow, doc) {
		return (workflow.conditions || []).every(({ field, condition, value }) => {
			const fieldtype = frappe.meta.get_docfield(workflow.document_type, field)?.fieldtype;
			return CONDITION_OPERATORS[condition](
				cast_condition_value(doc[field], fieldtype),
				cast_condition_value(value, fieldtype)
			);
		});
	},
	get_workflow: function (doc) {
		if (!doc) return null;
		frappe.workflow.setup(doc.doctype);
		return (
			(frappe.workflow.candidates[doc.doctype] || []).find((workflow) =>
				frappe.workflow.applies_to(workflow, doc)
			) || null
		);
	},
	has_workflow: function (doc) {
		return Boolean(frappe.workflow.get_workflow(doc));
	},
	get_state_fieldname: function (doctype) {
		if (frappe.workflow.state_fields[doctype] === undefined) {
			frappe.workflow.setup(doctype);
		}
		return frappe.workflow.state_fields[doctype];
	},
	get_default_state: function (doc, docstatus) {
		const workflow = resolve_workflow(doc);
		if (!workflow) return null;

		const default_state = (workflow.states || []).find(
			(state) => cint(state.doc_status) === cint(docstatus)
		);
		return default_state ? default_state.state : null;
	},
	get_transitions: function (doc) {
		frappe.workflow.setup(doc.doctype);
		return frappe.xcall("frappe.model.workflow.get_transitions", { doc: doc });
	},
	get_document_state_roles: function (doc, state) {
		const workflow = resolve_workflow(doc);
		if (!workflow) return [];

		return (frappe.get_children(workflow, "states", { state: state }) || []).map(
			(d) => d.allow_edit
		);
	},
	is_self_approval_enabled: function (doc) {
		return resolve_workflow(doc)?.allow_self_approval;
	},
	is_read_only: function (doctype, name) {
		var state_fieldname = frappe.workflow.get_state_fieldname(doctype);
		if (!state_fieldname) return false;

		var doc = locals[doctype][name];
		if (!doc) return false;
		if (doc.__islocal) return false;
		if (!frappe.workflow.has_workflow(doc)) return false;

		var state = doc[state_fieldname] || frappe.workflow.get_default_state(doc, doc.docstatus);
		if (!state) return false;

		let allow_edit_roles = frappe.workflow.get_document_state_roles(doc, state);
		return !frappe.user_roles.some((role) => allow_edit_roles.includes(role));
	},
	get_update_fields: function (doctype) {
		frappe.workflow.setup(doctype);
		const states = (frappe.workflow.candidates[doctype] || []).flatMap(
			(workflow) => workflow.states || []
		);
		return [...new Set(states.map((d) => d.update_field).filter(Boolean))];
	},
	get_state(doc) {
		const state_field = this.get_state_fieldname(doc.doctype);
		return doc[state_field] || this.get_default_state(doc, doc.docstatus);
	},
	get_all_transitions(doctype) {
		frappe.workflow.setup(doctype);
		return (frappe.workflow.candidates[doctype] || []).flatMap(
			(workflow) => workflow.transitions || []
		);
	},
	get_all_transition_actions(doctype) {
		return this.get_all_transitions(doctype).map((transition) => transition.action);
	},
};
