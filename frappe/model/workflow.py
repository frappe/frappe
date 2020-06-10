# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint
from frappe import _
from six import string_types
import json

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
def get_transitions(doc, workflow = None, raise_exception=False):
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
		if raise_exception:
			raise WorkflowStateError
		else:
			frappe.throw(_('Workflow State not set'), WorkflowStateError)

	transitions = []
	for transition in workflow.transitions:
		if transition.state == current_state and transition.allowed in roles:
			if not is_transition_condition_satisfied(transition, doc):
				continue
			transitions.append(transition.as_dict())
	return transitions

def get_workflow_safe_globals():
	# access to frappe.db.get_value and frappe.db.get_list
	return dict(
		frappe=frappe._dict(
			db=frappe._dict(
				get_value=frappe.db.get_value,
				get_list=frappe.db.get_list
			),
			session=frappe.session
		)
	)

def is_transition_condition_satisfied(transition, doc):
	if not transition.condition:
		return True
	else:
		return frappe.safe_eval(transition.condition, get_workflow_safe_globals(), dict(doc=doc.as_dict()))

@frappe.whitelist()
def apply_workflow(doc, action):
	'''Allow workflow action on the current doc'''
	doc = frappe.get_doc(frappe.parse_json(doc))
	workflow = get_workflow(doc.doctype)
	transitions = get_transitions(doc, workflow)
	user = frappe.session.user

	# find the transition
	transition = None
	for t in transitions:
		if t.action == action:
			transition = t

	if not transition:
		frappe.throw(_("Not a valid Workflow Action"), WorkflowTransitionError)

	if not has_approval_access(user, doc, transition):
		frappe.throw(_("Self approval is not allowed"))

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

@frappe.whitelist()
def can_cancel_document(doctype):
	workflow = get_workflow(doctype)
	for state_doc in workflow.states:
		if state_doc.doc_status == '2':
			for transition in workflow.transitions:
				if transition.next_state == state_doc.state:
					return False
			return True
	return True

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

	if not next_state:
		next_state = workflow.states[0].state
		doc.set(workflow.workflow_state_field, next_state)

	if not current_state:
		current_state = workflow.states[0].state

	state_row = [d for d in workflow.states if d.state == current_state]
	if not state_row:
		frappe.throw(_('{0} is not a valid Workflow State. Please update your Workflow and try again.'.format(frappe.bold(current_state))))
	state_row = state_row[0]

	# if transitioning, check if user is allowed to transition
	if current_state != next_state:
		bold_current = frappe.bold(current_state)
		bold_next = frappe.bold(next_state)

		if not doc._doc_before_save:
			# transitioning directly to a state other than the first
			# e.g from data import
			frappe.throw(_('Workflow State transition not allowed from {0} to {1}').format(bold_current, bold_next),
				WorkflowPermissionError)

		transitions = get_transitions(doc._doc_before_save)
		transition = [d for d in transitions if d.next_state == next_state]
		if not transition:
			frappe.throw(_('Workflow State transition not allowed from {0} to {1}').format(bold_current, bold_next),
				WorkflowPermissionError)

def get_workflow(doctype):
	return frappe.get_doc('Workflow', get_workflow_name(doctype))

def has_approval_access(user, doc, transition):
	return (user == 'Administrator'
		or transition.get('allow_self_approval')
		or user != doc.get('owner'))

def get_workflow_state_field(workflow_name):
	return get_workflow_field_value(workflow_name, 'workflow_state_field')

def send_email_alert(workflow_name):
	return get_workflow_field_value(workflow_name, 'send_email_alert')

def get_workflow_field_value(workflow_name, field):
	value = frappe.cache().hget('workflow_' + workflow_name, field)
	if value is None:
		value = frappe.db.get_value("Workflow", workflow_name, field)
		frappe.cache().hset('workflow_' + workflow_name, field, value)
	return value

@frappe.whitelist()
def bulk_workflow_approval(docnames, doctype, action):
	from collections import defaultdict

	# dictionaries for logging
	errored_transactions = defaultdict(list)
	successful_transactions = defaultdict(list)

	# WARN: message log is cleared
	print("Clearing frappe.message_log...")
	frappe.clear_messages()

	docnames = json.loads(docnames)
	for (idx, docname) in enumerate(docnames, 1):
		message_dict = {}
		try:
			show_progress(docnames, _('Applying: {0}').format(action), idx, docname)
			apply_workflow(frappe.get_doc(doctype, docname), action)
			frappe.db.commit()
		except Exception as e:
			if not frappe.message_log:
				# Exception is  raised manually and not from msgprint or throw
				message = "{0}".format(e.__class__.__name__)
				if e.args:
					message +=  " : {0}".format(e.args[0])
				message_dict = {"docname": docname, "message": message}
				errored_transactions[docname].append(message_dict)

			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), "Workflow {0} threw an error for {1} {2}".format(action, doctype, docname))
		finally:
			if not message_dict:
				if frappe.message_log:
					messages = frappe.get_message_log()
					for message in messages:
						frappe.message_log.pop()
						message_dict = {"docname": docname, "message": message.get("message")}

						if message.get("raise_exception", False):
							errored_transactions[docname].append(message_dict)
						else:
							successful_transactions[docname].append(message_dict)
				else:
					successful_transactions[docname].append({"docname": docname, "message": None})

	if errored_transactions and successful_transactions:
		indicator = "orange"
	elif errored_transactions:
		indicator  = "red"
	else:
		indicator = "green"

	print_workflow_log(errored_transactions, _("Errored Transactions"), doctype, indicator)
	print_workflow_log(successful_transactions, _("Successful Transactions"), doctype, indicator)

def print_workflow_log(messages, title, doctype, indicator):
	if messages.keys():
		msg = "<h4>{0}</h4>".format(title)

		for doc in messages.keys():
			if len(messages[doc]):
				html = "<details><summary>{0}</summary>".format(frappe.utils.get_link_to_form(doctype, doc))
				for log in messages[doc]:
					if log.get('message'):
						html += "<div class='small text-muted' style='padding:2.5px'>{0}</div>".format(log.get('message'))
				html += "</details>"
			else:
				html = "<div>{0}</div>".format(doc)
			msg += html

		frappe.msgprint(msg, title=_("Workflow Status"), indicator=indicator)

@frappe.whitelist()
def get_common_transition_actions(docs, doctype):
	common_actions = []
	if isinstance(docs, string_types):
		docs = json.loads(docs)
	try:
		for (i, doc) in enumerate(docs, 1):
			if not doc.get('doctype'):
				doc['doctype'] = doctype
			actions = [t.get('action') for t in get_transitions(doc, raise_exception=True) \
				if has_approval_access(frappe.session.user, doc, t)]
			if not actions: return []
			common_actions = actions if i == 1 else set(common_actions).intersection(actions)
			if not common_actions: return []
	except WorkflowStateError:
		pass

	return list(common_actions)

def show_progress(docnames, message, i, description):
	n = len(docnames)
	if n >= 5:
		frappe.publish_progress(
			float(i) * 100 / n,
			title = message,
			description = description
		)


def set_workflow_state_on_action(doc, workflow_name, action):
	workflow = frappe.get_doc('Workflow', workflow_name)
	workflow_state_field = workflow.workflow_state_field

	# If workflow state of doc is already correct, don't set workflow state
	for state in workflow.states:
		if state.state == doc.get(workflow_state_field) and doc.docstatus == cint(state.doc_status):
			return

	action_map = {
		'update_after_submit': '1',
		'submit': '1',
		'cancel': '2'
	}
	docstatus = action_map[action]
	for state in workflow.states:
		if state.doc_status == docstatus:
			doc.set(workflow_state_field, state.state)
			return 