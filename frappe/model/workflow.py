# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint
from frappe import _

class WorkflowStateError(frappe.ValidationError): pass
class WorkflowTransitionError(frappe.ValidationError): pass
class WorkflowPermissionError(frappe.ValidationError): pass

def get_workflow_name(doctype):
	workflow_name = frappe.cache().hget('workflow', doctype)
	if workflow_name is None:
		workflow_name = frappe.db.get_value("Workflow", {"document_type": doctype,
			"is_active": 1}, "name")
		frappe.cache().hset('workflow', doctype, workflow_name or '')

	return workflow_name

@frappe.whitelist()
def get_transitions(doc, workflow = None):
	'''Return list of possible transitions for the given doc'''
	doc = frappe.get_doc(frappe.parse_json(doc))

	if doc.is_new():
		return []

	frappe.has_permission(doc, 'read', throw=True)
	roles = frappe.get_roles()

	if not workflow:
		workflow = get_workflow(doc.doctype)
	current_state = doc.get(workflow.workflow_state_field)

	if not current_state:
		frappe.throw(_('Workflow State not set'), WorkflowStateError)

	transitions = []
	for transition in workflow.transitions:
		if transition.state == current_state and transition.allowed in roles:
			if transition.condition:
				# if condition, evaluate
				# access to frappe.db.get_value and frappe.db.get_list
				success = frappe.safe_eval(transition.condition,
					dict(frappe = frappe._dict(
						db = frappe._dict(get_value = frappe.db.get_value, get_list=frappe.db.get_list),
						session = frappe.session
					)),
					dict(doc = doc))
				if not success:
					continue
			transitions.append(transition.as_dict())

	return transitions

@frappe.whitelist()
def apply_workflow(doc, action):
	'''Allow workflow action on the current doc'''
	doc = frappe.get_doc(frappe.parse_json(doc))
	workflow = get_workflow(doc.doctype)
	transitions = get_transitions(doc, workflow)

	# find the transition
	transition = None
	for t in transitions:
		if t.action == action:
			transition = t

	if not transition:
		frappe.throw(_("Not a valid Workflow Action"), WorkflowTransitionError)

	# update workflow state field
	doc.set(workflow.workflow_state_field, transition.next_state)

	# find settings for the next state
	next_state = [d for d in workflow.states if d.state == transition.next_state][0]

	# update any additional field
	if next_state.update_field:
		doc.set(next_state.update_field, next_state.update_value)

	new_docstatus = cint(next_state.doc_status)
	if doc.docstatus == 0 and new_docstatus == 0:
		doc.save()
	elif doc.docstatus == 0 and new_docstatus == 1:
		doc.submit()
	elif doc.docstatus == 1 and new_docstatus == 1:
		doc.save()
	elif doc.docstatus == 1 and new_docstatus == 2:
		doc.cancel()
	else:
		frappe.throw(_('Illegal Document Status for {0}').format(next_state.state))

	doc.add_comment('Workflow', _(next_state.state))

	return doc

def validate_workflow(doc):
	'''Validate Workflow State and Transition for the current user.

	- Check if user is allowed to edit in current state
	- Check if user is allowed to transition to the next state (if changed)
	'''
	workflow = get_workflow(doc.doctype)

	current_state = None
	if getattr(doc, '_doc_before_save', None):
		current_state = doc._doc_before_save.get(workflow.workflow_state_field)
	next_state = doc.get(workflow.workflow_state_field)

	if not next_state or not current_state:
		# set default state (maybe not set in insert)
		current_state = next_state = workflow.states[0].state
		doc.set(workflow.workflow_state_field, workflow.states[0].state)

	state_row = [d for d in workflow.states if d.state == current_state]
	if not state_row:
		frappe.throw(_('{0} is not a valid Workflow State. Please update your Workflow and try again.'.format(frappe.bold(current_state))))
	state_row = state_row[0]

	# check if user is allowed to edit in current state
	if not state_row.allow_edit in frappe.get_roles():
		frappe.throw(_('Not allowed to edit in Workflow State {0}'.format(frappe.bold(current_state))), WorkflowPermissionError)

	# if transitioning, check if user is allowed to transition
	if current_state != next_state:
		transitions = get_transitions(doc._doc_before_save)
		transition = [d for d in transitions if d.next_state == next_state]
		if not transition:
			frappe.throw(_('Workflow State {0} is not allowed').format(frappe.bold(next_state)), WorkflowPermissionError)

def get_workflow(doctype):
	return frappe.get_doc('Workflow', get_workflow_name(doctype))
