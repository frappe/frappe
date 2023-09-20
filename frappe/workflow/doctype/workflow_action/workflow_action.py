# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.desk.form.utils import get_pdf_link
from frappe.desk.notifications import clear_doctype_notifications
from frappe.model.document import Document
from frappe.model.workflow import (
	apply_workflow,
	get_workflow_name,
	get_workflow_state_field,
	has_approval_access,
	is_transition_condition_satisfied,
	send_email_alert,
)
from frappe.query_builder import DocType
from frappe.utils import get_datetime, get_url
from frappe.utils.background_jobs import enqueue
from frappe.utils.data import get_link_to_form
from frappe.utils.user import get_users_with_role
from frappe.utils.verified_command import get_signed_params, verify_request


class WorkflowAction(Document):
	pass


def on_doctype_update():
	# The search order in any use case is no ["reference_name", "reference_doctype", "status"]
	# The index scan would happen from left to right
	# so even if status is not in the where clause the index will be used
	frappe.db.add_index("Workflow Action", ["reference_name", "reference_doctype", "status"])


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = frappe.get_roles(user)

	WorkflowAction = DocType("Workflow Action")
	WorkflowActionPermittedRole = DocType("Workflow Action Permitted Role")

	permitted_workflow_actions = (
		frappe.qb.from_(WorkflowAction)
		.join(WorkflowActionPermittedRole)
		.on(WorkflowAction.name == WorkflowActionPermittedRole.parent)
		.select(WorkflowAction.name)
		.where(WorkflowActionPermittedRole.role.isin(roles))
	).get_sql()

	return """(`tabWorkflow Action`.`name` in ({permitted_workflow_actions})
		or `tabWorkflow Action`.`user`={user})
		and `tabWorkflow Action`.`status`='Open'
	""".format(
		permitted_workflow_actions=permitted_workflow_actions, user=frappe.db.escape(user)
	)


def has_permission(doc, user):

	user_roles = set(frappe.get_roles(user))

	permitted_roles = {permitted_role.role for permitted_role in doc.permitted_roles}

	return user == "Administrator" or user_roles.intersection(permitted_roles)


def process_workflow_actions(doc, state):
	workflow = get_workflow_name(doc.get("doctype"))
	if not workflow:
		return

	if state == "on_trash":
		clear_workflow_actions(doc.get("doctype"), doc.get("name"))
		return

	if is_workflow_action_already_created(doc):
		return

	update_completed_workflow_actions(
		doc, workflow=workflow, workflow_state=get_doc_workflow_state(doc)
	)
	clear_doctype_notifications("Workflow Action")

	next_possible_transitions = get_next_possible_transitions(
		workflow, get_doc_workflow_state(doc), doc
	)

	if not next_possible_transitions:
		return

	user_data_map, roles = get_users_next_action_data(next_possible_transitions, doc)

	if not user_data_map:
		return

	create_workflow_actions_for_roles(roles, doc)

	if send_email_alert(workflow):
		enqueue(
			send_workflow_action_email, queue="short", users_data=list(user_data_map.values()), doc=doc
		)


@frappe.whitelist(allow_guest=True)
def apply_action(action, doctype, docname, current_state, user=None, last_modified=None):
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


@frappe.whitelist(allow_guest=True)
def confirm_action(doctype, docname, user, action):
	if not verify_request():
		return

	logged_in_user = frappe.session.user
	if logged_in_user == "Guest" and user:
		# to allow user to apply action without login
		frappe.set_user(user)

	doc = frappe.get_doc(doctype, docname)
	newdoc = apply_workflow(doc, action)
	frappe.db.commit()
	return_success_page(newdoc)

	# reset session user
	if logged_in_user == "Guest":
		frappe.set_user(logged_in_user)


def return_success_page(doc):
	frappe.respond_as_web_page(
		_("Success"),
		_("{0}: {1} is set to state {2}").format(
			doc.get("doctype"), frappe.bold(doc.get("name")), frappe.bold(get_doc_workflow_state(doc))
		),
		indicator_color="green",
	)


def return_action_confirmation_page(doc, action, action_link, alert_doc_change=False):
	template_params = {
		"title": doc.get("name"),
		"doctype": doc.get("doctype"),
		"docname": doc.get("name"),
		"action": action,
		"action_link": action_link,
		"alert_doc_change": alert_doc_change,
	}

	template_params["pdf_link"] = get_pdf_link(doc.get("doctype"), doc.get("name"))

	frappe.respond_as_web_page(
		title=None,
		html=None,
		indicator_color="blue",
		template="confirm_workflow_action",
		context=template_params,
	)


def return_link_expired_page(doc, doc_workflow_state):
	frappe.respond_as_web_page(
		_("Link Expired"),
		_("Document {0} has been set to state {1} by {2}").format(
			frappe.bold(doc.get("name")),
			frappe.bold(doc_workflow_state),
			frappe.bold(frappe.get_value("User", doc.get("modified_by"), "full_name")),
		),
		indicator_color="blue",
	)


def update_completed_workflow_actions(doc, user=None, workflow=None, workflow_state=None):
	allowed_roles = get_allowed_roles(user, workflow, workflow_state)
	# There is no transaction leading upto this state
	# so no older actions to complete
	if not allowed_roles:
		return
	if workflow_action := get_workflow_action_by_role(doc, allowed_roles):
		update_completed_workflow_actions_using_role(user, workflow_action)
	else:
		# backwards compatibility
		# for workflow actions saved using user
		clear_old_workflow_actions_using_user(doc, user)
		update_completed_workflow_actions_using_user(doc, user)


def get_allowed_roles(user, workflow, workflow_state):
	user = user if user else frappe.session.user

	allowed_roles = frappe.get_all(
		"Workflow Transition",
		fields="allowed",
		filters=[["parent", "=", workflow], ["next_state", "=", workflow_state]],
		pluck="allowed",
	)

	user_roles = set(frappe.get_roles(user))
	return set(allowed_roles).intersection(user_roles)


def get_workflow_action_by_role(doc, allowed_roles):
	WorkflowAction = DocType("Workflow Action")
	WorkflowActionPermittedRole = DocType("Workflow Action Permitted Role")
	return (
		frappe.qb.from_(WorkflowAction)
		.join(WorkflowActionPermittedRole)
		.on(WorkflowAction.name == WorkflowActionPermittedRole.parent)
		.select(WorkflowAction.name, WorkflowActionPermittedRole.role)
		.where(
			(WorkflowAction.reference_name == doc.get("name"))
			& (WorkflowAction.reference_doctype == doc.get("doctype"))
			& (WorkflowAction.status == "Open")
			& (WorkflowActionPermittedRole.role.isin(list(allowed_roles)))
		)
		.orderby(WorkflowActionPermittedRole.role)
		.limit(1)
	).run(as_dict=True)


def update_completed_workflow_actions_using_role(user=None, workflow_action=None):
	user = user if user else frappe.session.user
	WorkflowAction = DocType("Workflow Action")

	if not workflow_action:
		return

	(
		frappe.qb.update(WorkflowAction)
		.set(WorkflowAction.status, "Completed")
		.set(WorkflowAction.completed_by, user)
		.set(WorkflowAction.completed_by_role, workflow_action[0].role)
		.where(WorkflowAction.name == workflow_action[0].name)
	).run()


def clear_old_workflow_actions_using_user(doc, user=None):
	user = user if user else frappe.session.user

	if frappe.db.has_column("Workflow Action", "user"):
		frappe.db.delete(
			"Workflow Action",
			{
				"reference_name": doc.get("name"),
				"reference_doctype": doc.get("doctype"),
				"status": "Open",
				"user": ("!=", user),
			},
		)


def update_completed_workflow_actions_using_user(doc, user=None):
	user = user or frappe.session.user

	if frappe.db.has_column("Workflow Action", "user"):
		WorkflowAction = DocType("Workflow Action")
		(
			frappe.qb.update(WorkflowAction)
			.set(WorkflowAction.status, "Completed")
			.set(WorkflowAction.completed_by, user)
			.where(
				(WorkflowAction.reference_name == doc.get("name"))
				& (WorkflowAction.reference_doctype == doc.get("doctype"))
				& (WorkflowAction.status == "Open")
				& (WorkflowAction.user == user)
			)
		).run()


def get_next_possible_transitions(workflow_name, state, doc=None):
	transitions = frappe.get_all(
		"Workflow Transition",
		fields=["allowed", "action", "state", "allow_self_approval", "next_state", "`condition`"],
		filters=[["parent", "=", workflow_name], ["state", "=", state]],
	)

	transitions_to_return = []

	for transition in transitions:
		is_next_state_optional = get_state_optional_field_value(workflow_name, transition.next_state)
		# skip transition if next state of the transition is optional
		if is_next_state_optional:
			continue
		if not is_transition_condition_satisfied(transition, doc):
			continue
		transitions_to_return.append(transition)

	return transitions_to_return


def get_users_next_action_data(transitions, doc):
	roles = set()
	user_data_map = {}
	for transition in transitions:
		roles.add(transition.allowed)
		users = get_users_with_role(transition.allowed)
		filtered_users = filter_allowed_users(users, doc, transition)
		for user in filtered_users:
			if not user_data_map.get(user):
				user_data_map[user] = frappe._dict(
					{
						"possible_actions": [],
						"email": frappe.db.get_value("User", user, "email"),
					}
				)

			user_data_map[user].get("possible_actions").append(
				frappe._dict(
					{
						"action_name": transition.action,
						"action_link": get_workflow_action_url(transition.action, doc, user),
					}
				)
			)
	return user_data_map, roles


def create_workflow_actions_for_roles(roles, doc):
	workflow_action = frappe.get_doc(
		{
			"doctype": "Workflow Action",
			"reference_doctype": doc.get("doctype"),
			"reference_name": doc.get("name"),
			"workflow_state": get_doc_workflow_state(doc),
			"status": "Open",
		}
	)

	for role in roles:
		workflow_action.append("permitted_roles", {"role": role})

	workflow_action.insert(ignore_permissions=True)


def send_workflow_action_email(users_data, doc):
	common_args = get_common_email_args(doc)
	message = common_args.pop("message", None)
	for d in users_data:
		email_args = {
			"recipients": [d.get("email")],
			"args": {"actions": list(deduplicate_actions(d.get("possible_actions"))), "message": message},
			"reference_name": doc.name,
			"reference_doctype": doc.doctype,
		}
		email_args.update(common_args)
		try:
			frappe.sendmail(**email_args)
		except frappe.OutgoingEmailError:
			# Emails config broken, don't bother retrying next user.
			frappe.log_error("Failed to send workflow action email")
			return


def deduplicate_actions(action_list):
	action_map = {}
	for action_data in action_list:
		if not action_map.get(action_data.action_name):
			action_map[action_data.action_name] = action_data

	return action_map.values()


def get_workflow_action_url(action, doc, user):
	apply_action_method = (
		"/api/method/frappe.workflow.doctype.workflow_action.workflow_action.apply_action"
	)

	params = {
		"doctype": doc.get("doctype"),
		"docname": doc.get("name"),
		"action": action,
		"current_state": get_doc_workflow_state(doc),
		"user": user,
		"last_modified": doc.get("modified"),
	}

	return get_url(apply_action_method + "?" + get_signed_params(params))


def get_confirm_workflow_action_url(doc, action, user):
	confirm_action_method = (
		"/api/method/frappe.workflow.doctype.workflow_action.workflow_action.confirm_action"
	)

	params = {
		"action": action,
		"doctype": doc.get("doctype"),
		"docname": doc.get("name"),
		"user": user,
	}

	return get_url(confirm_action_method + "?" + get_signed_params(params))


def is_workflow_action_already_created(doc):
	return frappe.db.exists(
		{
			"doctype": "Workflow Action",
			"reference_name": doc.get("name"),
			"reference_doctype": doc.get("doctype"),
			"workflow_state": get_doc_workflow_state(doc),
		}
	)


def clear_workflow_actions(doctype, name):
	if not (doctype and name):
		return
	frappe.db.delete(
		"Workflow Action",
		filters={
			"reference_name": name,
			"reference_doctype": doctype,
		},
	)


def get_doc_workflow_state(doc):
	workflow_name = get_workflow_name(doc.get("doctype"))
	workflow_state_field = get_workflow_state_field(workflow_name)
	return doc.get(workflow_state_field)


def filter_allowed_users(users, doc, transition):
	"""Filters list of users by checking if user has access to doc and
	if the user satisfies 'workflow transision self approval' condition
	"""
	from frappe.permissions import has_permission

	filtered_users = []
	for user in users:
		if has_approval_access(user, doc, transition) and has_permission(
			doctype=doc, user=user, raise_exception=False
		):
			filtered_users.append(user)
	return filtered_users


def get_common_email_args(doc):
	doctype = doc.get("doctype")
	docname = doc.get("name")

	email_template = get_email_template(doc)
	if email_template:
		subject = frappe.render_template(email_template.subject, vars(doc))
		response = frappe.render_template(email_template.response, vars(doc))
	else:
		subject = _("Workflow Action") + f" on {doctype}: {docname}"
		response = get_link_to_form(doctype, docname, f"{doctype}: {docname}")

	common_args = {
		"template": "workflow_action",
		"header": "Workflow Action",
		"attachments": [frappe.attach_print(doctype, docname, file_name=docname, doc=doc)],
		"subject": subject,
		"message": response,
	}
	return common_args


def get_email_template(doc):
	"""Returns next_action_email_template
	for workflow state (if available) based on doc current workflow state
	"""
	workflow_name = get_workflow_name(doc.get("doctype"))
	doc_state = get_doc_workflow_state(doc)
	template_name = frappe.db.get_value(
		"Workflow Document State",
		{"parent": workflow_name, "state": doc_state},
		"next_action_email_template",
	)

	if not template_name:
		return
	return frappe.get_doc("Email Template", template_name)


def get_state_optional_field_value(workflow_name, state):
	return frappe.get_cached_value(
		"Workflow Document State", {"parent": workflow_name, "state": state}, "is_optional_state"
	)
