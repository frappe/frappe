# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public workflow API — inspect and apply workflow transitions on documents.

Endpoints were consolidated from `frappe.model.workflow`, the Workflow
doctype and the Workflow Action doctype; the old dotted paths keep working
via aliases in the original modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.docstatus import DocStatus
from frappe.model.workflow import (
	DEFAULT_WORKFLOW_TASKS,
	WorkflowStateError,
	WorkflowTransitionError,
	_bulk_workflow_action,
	evaluate_workflow_value,
	get_workflow,
	has_approval_access,
	is_transition_condition_satisfied,
)
from frappe.public_api import public
from frappe.utils import get_datetime
from frappe.utils.verified_command import verify_request

if TYPE_CHECKING:
	from datetime import datetime

	from frappe.model.document import Document
	from frappe.workflow.doctype.workflow.workflow import Workflow


@public(group="Workflow")
@frappe.whitelist()
def get_transitions(
	doc: Document | str | dict, workflow: Workflow | None = None, raise_exception: bool = False
) -> list[dict]:
	"""Return the list of possible workflow transitions for the given doc.

	:param doc: the document (or its dict/JSON) to get transitions for
	:param workflow: the applicable Workflow, determined from the doctype if not passed
	:param raise_exception: raise WorkflowStateError instead of throwing a message
	:return: The transitions allowed for the current user from the doc's current state.
	"""
	from frappe.model.document import Document

	if not isinstance(doc, Document):
		doc = frappe.get_doc(frappe.parse_json(doc))
		doc.load_from_db()

	if doc.is_new():
		return []

	doc.check_permission("read")

	workflow = workflow or get_workflow(doc.doctype)
	current_state = doc.get(workflow.workflow_state_field)

	if not current_state:
		if raise_exception:
			raise WorkflowStateError
		else:
			frappe.throw(_("Workflow State not set"), WorkflowStateError)

	transitions = []
	roles = frappe.get_roles()

	for transition in workflow.transitions:
		if transition.state == current_state and transition.allowed in roles:
			if not is_transition_condition_satisfied(transition, doc):
				continue
			transitions.append(transition.as_dict())

	return transitions


@public(group="Workflow")
@frappe.whitelist()
def apply_workflow(doc: Document | str | dict, action: str) -> Document | None:
	"""Apply a workflow action (transition) on a document.

	Validates that the transition is allowed for the current user, updates the
	workflow state, runs transition tasks and saves/submits/cancels the
	document as dictated by the next state.

	:param doc: the document (or its dict/JSON) to apply the action on
	:param action: name of the workflow action to apply
	:return: The updated document, or None if the state change was queued for
		background submission.
	"""
	doc = frappe.get_doc(frappe.parse_json(doc))
	doc.load_from_db()
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
	next_state = next(d for d in workflow.states if d.state == transition.next_state)

	# update any additional field
	if next_state.update_field:
		update_value = evaluate_workflow_value(
			next_state.update_value, next_state.evaluate_as_expression, doc
		)
		doc.set(next_state.update_field, update_value)

	if transition.transition_tasks:
		workflow_transitions = frappe.db.get_all(
			"Workflow Transition Task",
			{"parent": transition.transition_tasks, "enabled": True},
			["task", "link", "asynchronous"],
			order_by="idx",
		)

		"""app-specific actions defined by the user
		Example:
		def create_customer(doc):
			<your-code>

		this goes in the hooks.py
		workflow_methods = [{"name": "Create a customer", "method":
					 		"frappe.dotted.path.create_customer"}]
		"""

		tasks = {i["name"]: i["method"] for i in frappe.get_hooks("workflow_methods")}

		sync_tasks = []
		async_tasks = []
		for workflow_transition in workflow_transitions:
			# edge-case with user-defined server scripts
			if workflow_transition.task in DEFAULT_WORKFLOW_TASKS:
				match workflow_transition.task:
					case "Webhook":
						webhook = frappe.get_doc("Webhook", workflow_transition.link)
						task_method = webhook.execute_for_doc

					case "Server Script":
						server_script = frappe.get_doc("Server Script", workflow_transition.link)
						task_method = server_script.execute_workflow_task

			else:  # normal app-defined tasks
				try:
					task_method = frappe.get_attr(tasks[workflow_transition.task])
				except KeyError:
					frappe.throw(_('There is no task called "{}"').format(workflow_transition.task))

			if workflow_transition.asynchronous:
				async_tasks.append(task_method)
			else:
				sync_tasks.append(task_method)

		# will execute in the same transaction as the rest of the transition
		for sync_task in sync_tasks:
			sync_task(doc)

		# will spawn separate background jobs. Use for asynchronous, optional tasks.
		for async_task in async_tasks:
			frappe.enqueue(async_task, doc=doc, enqueue_after_commit=True)

	new_docstatus = DocStatus(next_state.doc_status or 0)
	if doc.docstatus.is_draft() and new_docstatus.is_draft():
		doc.save()
	elif doc.docstatus.is_draft() and new_docstatus.is_submitted():
		from frappe.core.doctype.submission_queue.submission_queue import queue_submission
		from frappe.utils.scheduler import is_scheduler_inactive

		if doc.meta.queue_in_background and not is_scheduler_inactive():
			queue_submission(doc, "Submit")
			return

		doc.submit()
	elif doc.docstatus.is_submitted() and new_docstatus.is_submitted():
		doc.save()
	elif doc.docstatus.is_submitted() and new_docstatus.is_cancelled():
		if doc.meta.queue_in_background and not is_scheduler_inactive():
			queue_submission(doc, "Cancel")
			return

		doc.cancel()
	else:
		frappe.throw(_("Illegal Document Status for {0}").format(next_state.state))

	doc.add_comment("Workflow", _(next_state.state))

	return doc


@public(group="Workflow")
@frappe.whitelist()
def can_cancel_document(doctype: str) -> bool:
	"""Check whether documents of this doctype can be cancelled directly.

	Cancellation must happen through a workflow transition when the workflow
	defines one that leads to a cancelling state.

	:param doctype: DocType governed by a workflow
	:return: True if direct cancellation is allowed.
	"""
	workflow = get_workflow(doctype)
	cancelling_states = [s.state for s in workflow.states if s.doc_status == "2"]
	if not cancelling_states:
		return True

	for transition in workflow.transitions:
		if transition.next_state in cancelling_states:
			return False
	return True


@public(group="Workflow")
@frappe.whitelist()
def bulk_workflow_approval(docnames: str | list, doctype: str, action: str) -> None:
	"""Apply a workflow action on multiple documents.

	Runs inline for small batches and in the background for up to 500
	documents.

	:param docnames: names of the documents to apply the action on
	:param doctype: DocType of the documents
	:param action: name of the workflow action to apply
	"""
	docnames = frappe.parse_json(docnames)
	if len(docnames) < 20:
		_bulk_workflow_action(docnames, doctype, action)
	elif len(docnames) <= 500:
		frappe.msgprint(_("Bulk {0} is enqueued in background.").format(action), alert=True)
		frappe.enqueue(
			_bulk_workflow_action,
			docnames=docnames,
			doctype=doctype,
			action=action,
			queue="short",
			timeout=1000,
			at_front_when_starved=True,
		)
	else:
		frappe.throw(_("Bulk approval only support up to 500 documents."), title=_("Too Many Documents"))


@public(group="Workflow")
@frappe.whitelist()
def get_common_transition_actions(docs: str | list[dict[str, Any]], doctype: str) -> list:
	"""Return the workflow actions applicable to all of the given documents.

	:param docs: the documents (or their dicts/JSON) to intersect actions for
	:param doctype: DocType of the documents
	:return: Actions the current user may apply to every one of the documents.
	"""
	common_actions = []
	docs = frappe.parse_json(docs)
	try:
		for i, doc in enumerate(docs, 1):
			if not doc.get("doctype"):
				doc["doctype"] = doctype
			actions = [
				t.get("action")
				for t in get_transitions(doc, raise_exception=True)
				if has_approval_access(frappe.session.user, doc, t)
			]
			if not actions:
				return []
			common_actions = actions if i == 1 else set(common_actions).intersection(actions)
			if not common_actions:
				return []
	except WorkflowStateError:
		pass

	return list(common_actions)


@public(group="Workflow")
@frappe.whitelist()
def get_workflow_state_count(
	doctype: str, workflow_state_field: str, states: str | list[str]
) -> list[dict] | None:
	"""Count documents per workflow state, excluding the given states.

	:param doctype: DocType governed by a workflow
	:param workflow_state_field: fieldname that holds the workflow state
	:param states: states to exclude from the count (typically closed states)
	:return: One dict per remaining state with the state value and its `count`.
	"""
	frappe.has_permission(doctype=doctype, ptype="read", throw=True)
	states = frappe.parse_json(states)

	if workflow_state_field in frappe.get_meta(doctype).get_valid_columns():
		result = frappe.get_all(
			doctype,
			fields=[workflow_state_field, {"COUNT": "*", "as": "count"}],
			filters={workflow_state_field: ["not in", states]},
			group_by=workflow_state_field,
		)
		return [r for r in result if r[workflow_state_field]]


@public(group="Workflow")
@frappe.whitelist(methods=["GET"])
def get_workflow_methods() -> list[str]:
	"""Return the names of available workflow transition tasks.

	:return: Task names from the `workflow_methods` hook plus the built-in tasks.
	"""
	return [i["name"] for i in frappe.get_hooks("workflow_methods")] + DEFAULT_WORKFLOW_TASKS


@public(group="Workflow")
@frappe.whitelist(allow_guest=True)
def apply_action(
	action: str,
	doctype: str,
	docname: str | int,
	current_state: str,
	user: str | None = None,
	last_modified: str | datetime | None = None,
) -> None:
	"""Open the confirmation page for a workflow action from a signed email link.

	Verifies the request signature and responds with a confirmation page (or a
	link-expired page if the document moved on).

	:param action: name of the workflow action
	:param doctype: DocType of the document
	:param docname: name of the document
	:param current_state: workflow state the document had when the link was sent
	:param user: user the action link was sent to
	:param last_modified: modification timestamp of the document when the link was sent
	"""
	from frappe.workflow.doctype.workflow_action.workflow_action import (
		get_confirm_workflow_action_url,
		get_doc_workflow_state,
		return_action_confirmation_page,
		return_link_expired_page,
	)

	if not verify_request():
		return

	doc = frappe.get_doc(doctype, docname)
	doc_workflow_state = get_doc_workflow_state(doc)

	if doc_workflow_state == current_state:
		action_link = get_confirm_workflow_action_url(doc, action, user)

		if not last_modified or get_datetime(doc.modified) == get_datetime(last_modified):
			return_action_confirmation_page(doc, action, action_link)
		else:
			return_action_confirmation_page(doc, action, action_link, alert_doc_change=True)

	else:
		return_link_expired_page(doc, doc_workflow_state)


@public(group="Workflow")
@frappe.whitelist()
def confirm_action(doctype: str, docname: str | int, user: str, action: str) -> None:
	"""Apply a workflow action confirmed from a signed email link.

	:param doctype: DocType of the document
	:param docname: name of the document
	:param user: user confirming the action
	:param action: name of the workflow action to apply
	"""
	from frappe.workflow.doctype.workflow_action.workflow_action import return_success_page

	if not verify_request():
		return

	doc = frappe.get_doc(doctype, docname)
	newdoc = apply_workflow(doc, action)
	frappe.db.commit()
	return_success_page(newdoc)
