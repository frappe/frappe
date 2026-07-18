# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.docstatus import DocStatus
from frappe.utils import cint

if TYPE_CHECKING:
	from frappe.model.document import Document
	from frappe.workflow.doctype.workflow.workflow import Workflow


DEFAULT_WORKFLOW_TASKS = ["Webhook", "Server Script"]


class WorkflowStateError(frappe.ValidationError):
	pass


class WorkflowTransitionError(frappe.ValidationError):
	pass


class WorkflowPermissionError(frappe.ValidationError):
	pass


def get_workflow_name(doctype):
	workflow_name = frappe.cache.hget("workflow", doctype)
	if workflow_name is None:
		workflow_name = frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1}, "name")
		frappe.cache.hset("workflow", doctype, workflow_name or "")

	return workflow_name


def get_workflow_safe_globals():
	# access to frappe.db.get_value, frappe.db.get_list, and date time utils.
	return dict(
		frappe=frappe._dict(
			db=frappe._dict(get_value=frappe.db.get_value, get_list=frappe.db.get_list),
			session=frappe.session,
			utils=frappe._dict(
				now_datetime=frappe.utils.now_datetime,
				add_to_date=frappe.utils.add_to_date,
				get_datetime=frappe.utils.get_datetime,
				now=frappe.utils.now,
			),
		)
	)


def is_transition_condition_satisfied(transition, doc) -> bool:
	if not transition.condition:
		return True
	else:
		return frappe.safe_eval(transition.condition, get_workflow_safe_globals(), dict(doc=doc.as_dict()))


def evaluate_workflow_value(value, evaluate_as_expression, doc):
	if not value:
		return None
	if evaluate_as_expression:
		try:
			return frappe.safe_eval(value, get_workflow_safe_globals(), dict(doc=doc.as_dict()))
		except Exception as e:
			frappe.throw(
				_("Invalid expression in Workflow Update Value: {0}").format(str(e)),
				title=_("Workflow Evaluation Error"),
			)
	else:
		return value


def validate_workflow(doc):
	"""Validate Workflow State and Transition for the current user.

	- Check if user is allowed to edit in current state
	- Check if user is allowed to transition to the next state (if changed)
	"""
	workflow = get_workflow(doc.doctype)

	current_state = None
	if getattr(doc, "_doc_before_save", None):
		current_state = doc._doc_before_save.get(workflow.workflow_state_field)
	next_state = doc.get(workflow.workflow_state_field)

	if not next_state:
		next_state = workflow.states[0].state
		doc.set(workflow.workflow_state_field, next_state)

	if not current_state:
		current_state = workflow.states[0].state

	state_row = [d for d in workflow.states if d.state == current_state]
	if not state_row:
		frappe.throw(
			_("{0} is not a valid Workflow State. Please update your Workflow and try again.").format(
				frappe.bold(current_state)
			)
		)
	state_row = state_row[0]

	# if transitioning, check if user is allowed to transition
	if current_state != next_state:
		bold_current = frappe.bold(current_state)
		bold_next = frappe.bold(next_state)

		if not doc._doc_before_save:
			# transitioning directly to a state other than the first
			# e.g from data import
			frappe.throw(
				_("Workflow State transition not allowed from {0} to {1}").format(bold_current, bold_next),
				WorkflowPermissionError,
			)

		from frappe.core.api.workflow import get_transitions

		transitions = get_transitions(doc._doc_before_save)
		transition = [d for d in transitions if d.next_state == next_state]
		if not transition:
			frappe.throw(
				_("Workflow State transition not allowed from {0} to {1}").format(bold_current, bold_next),
				WorkflowPermissionError,
			)


def get_workflow(doctype) -> "Workflow":
	return frappe.get_cached_doc("Workflow", get_workflow_name(doctype))


def has_approval_access(user, doc, transition):
	return user == "Administrator" or transition.get("allow_self_approval") or user != doc.get("owner")


def get_workflow_state_field(workflow_name):
	return get_workflow_field_value(workflow_name, "workflow_state_field")


def send_email_alert(workflow_name):
	return get_workflow_field_value(workflow_name, "send_email_alert")


def get_workflow_field_value(workflow_name, field):
	return frappe.get_cached_value("Workflow", workflow_name, field)


def _bulk_workflow_action(docnames, doctype, action):
	# dictionaries for logging
	failed_transactions = defaultdict(list)
	successful_transactions = defaultdict(list)

	frappe.clear_messages()
	for idx, docname in enumerate(docnames, 1):
		message_dict = {}
		try:
			show_progress(docnames, _("Applying: {0}").format(action), idx, docname)
			from frappe.core.api.workflow import apply_workflow

			apply_workflow(frappe.get_doc(doctype, docname), action)
			frappe.db.commit()
		except Exception as e:
			if not frappe.message_log:
				# Exception is	raised manually and not from msgprint or throw
				message = f"{e.__class__.__name__}"
				if e.args:
					message += f" : {e.args[0]}"
				message_dict = {"docname": docname, "message": message}
				failed_transactions[docname].append(message_dict)

			frappe.db.rollback()
			frappe.log_error(
				title=f"Workflow {action} threw an error for {doctype} {docname}",
				reference_doctype="Workflow",
				reference_name=action,
			)
		finally:
			if not message_dict:
				if frappe.message_log:
					messages = frappe.get_message_log()
					for message in messages:
						frappe.message_log.pop()
						message_dict = {"docname": docname, "message": message.get("message")}

						if message.get("raise_exception", False) or "Error" in message.get("message", ""):
							failed_transactions[docname].append(message_dict)
						else:
							successful_transactions[docname].append(message_dict)
				else:
					successful_transactions[docname].append({"docname": docname, "message": None})

	assert all(
		docname in failed_transactions or docname in successful_transactions for docname in docnames
	), "every docname must be recorded as either a failed or successful transaction"

	if failed_transactions and successful_transactions:
		indicator = "orange"
	elif failed_transactions:
		indicator = "red"
	else:
		indicator = "green"

	print_workflow_log(failed_transactions, _("Failed Transactions"), doctype, indicator)
	print_workflow_log(successful_transactions, _("Successful Transactions"), doctype, indicator)


def print_workflow_log(messages, title, doctype, indicator):
	if messages.keys():
		msg = f"<h4>{title}</h4>"

		for doc in messages.keys():
			if len(messages[doc]):
				html = f"<details><summary>{frappe.utils.get_link_to_form(doctype, doc)}</summary>"
				for log in messages[doc]:
					if log.get("message"):
						html += "<div class='small text-muted' style='padding:2.5px'>{}</div>".format(
							log.get("message")
						)
				html += "</details>"
			else:
				html = f"<div>{doc}</div>"
			msg += html

		frappe.msgprint(
			msg, title=_("Workflow Status"), indicator=indicator, is_minimizable=True, realtime=True
		)


def show_progress(docnames, message, i, description):
	n = len(docnames)
	if n >= 5:
		frappe.publish_progress(float(i) * 100 / n, title=message, description=description)


def set_workflow_state_on_action(doc, workflow_name, action):
	workflow = frappe.get_doc("Workflow", workflow_name)
	workflow_state_field = workflow.workflow_state_field

	# If workflow state of doc is already correct, don't set workflow state
	for state in workflow.states:
		if state.state == doc.get(workflow_state_field) and doc.docstatus == cint(state.doc_status):
			return

	action_map = {"update_after_submit": "1", "submit": "1", "cancel": "2"}
	docstatus = action_map[action]
	for state in workflow.states:
		if state.doc_status == docstatus:
			doc.set(workflow_state_field, state.state)
			return


# `get_transitions`, `apply_workflow`, `can_cancel_document`, `bulk_workflow_approval`, `get_common_transition_actions` moved to frappe.core.api.workflow.
# The aliases keep the old dotted paths working; resolved lazily to avoid
# circular imports.
_MOVED_TO_WORKFLOW_API = {
	"get_transitions": "get_transitions",
	"apply_workflow": "apply_workflow",
	"can_cancel_document": "can_cancel_document",
	"bulk_workflow_approval": "bulk_workflow_approval",
	"get_common_transition_actions": "get_common_transition_actions",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_WORKFLOW_API.get(name):
		from frappe.core.api import workflow

		return getattr(workflow, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
