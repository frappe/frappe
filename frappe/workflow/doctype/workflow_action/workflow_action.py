# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.page.permission_manager.permission_manager import get_users_with_role
from frappe.utils.background_jobs import enqueue
from frappe.utils import get_url
from frappe.utils.verified_command import get_signed_params, verify_request
from frappe import _
from frappe.model.workflow import apply_workflow, get_workflow_name

class WorkflowAction(Document):
	pass


def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	if user == "Administrator": return ""

	return "(`tabWorkflow Action`.user='{user}')".format(user=user)


def has_permission(doc, user):
	if user not in ['Administrator', doc.user]:
		return False


def create_workflow_actions(doc, state):

	reference_doctype = doc.doctype
	reference_name = doc.name
	workflow = get_workflow_name(reference_doctype)

	if not workflow: return

	workflow = frappe.get_doc('Workflow', workflow)

	doc_current_state = doc.get(workflow.workflow_state_field)

	# hack to check if workflow action was already created and is this method called again due some field changes
	workflow_action_already_created = frappe.db.count('Workflow Action', {
		'reference_doctype': reference_doctype,
		'reference_name': reference_name,
		'workflow_state': doc_current_state
	})

	if workflow_action_already_created: return

	immediate_next_possible_transitions = [d for d in workflow.transitions if d.state == doc_current_state]

	current_user = frappe.session.user

	# update status of completed workflow action of user
	frappe.db.sql('''update `tabWorkflow Action` set status='Completed', completed_by=%s
		where reference_doctype=%s and reference_name=%s and user=%s''',
		(current_user, reference_doctype, reference_name, current_user))

	# delete irrelevant workflow actions
	frappe.db.sql('''delete from `tabWorkflow Action`
		where reference_doctype=%s and reference_name=%s and user!=%s''',
		(reference_doctype, reference_name, current_user))


	from frappe.permissions import has_permission

	email_map = {}

	for transition in immediate_next_possible_transitions:
		users = get_users_with_role(transition.allowed)
		for user in users:
			if not has_permission(doctype=doc, ptype='read', user=user): continue

			if not email_map.get(user):
				email_map[user] = {
					'possible_actions': [],
					'email': frappe.db.get_value('User', user, 'email'),
				}

			email_map[user].get('possible_actions').append({
				'action_name': transition.action,
				'action_link': get_workflow_action_url(
					transition.action,
					reference_doctype,
					reference_name,
					doc_current_state)
			})

	for user in email_map.keys():
		newdoc = frappe.get_doc({
				'doctype': 'Workflow Action',
				'reference_doctype': reference_doctype,
				'reference_name': reference_name,
				'workflow_state': doc_current_state,
				'status': 'Open',
				'user': user
			})
		newdoc.insert(ignore_permissions=True)

	frappe.db.commit()
	if email_map:
		send_workflow_action_email(email_map, reference_doctype, reference_name)


def send_workflow_action_email(email_map, doctype, docname):
	email_message = _('{0}:{1}'.format(doctype, docname))
	common_args = {
		'template': 'workflow_action',
		'attachments': [frappe.attach_print(doctype, docname , file_name=docname)],
		'header': [_("Workflow Action"), "orange"],
		'subject': _('Workflow Action')
	}

	for d in email_map.values():
		email_args = {
			'recipients': [d.get('email')],
			'args': {
				'actions': d.get('possible_actions'),
				'message': _('{0} : {1}'.format(doctype, docname))
			},
		}
		email_args.update(common_args)
		enqueue(method=frappe.sendmail, queue='short', **email_args)


@frappe.whitelist()
def apply_action(action, doctype, docname, current_state):
	doc = frappe.get_doc(doctype, docname)
	workflow = get_workflow_name(doctype)
	doc_workflow_state = doc.get(
		frappe.get_value('Workflow', workflow, 'workflow_state_field')
	)

	if doc_workflow_state == current_state:
		try:
			apply_workflow(doc, action)
			frappe.respond_as_web_page(_("Success"),
				_("Done"),
				indicator_color='green')
		except Exception as e:
			frappe.respond_as_web_page(_("Error"), e,
				indicator_color='red')
	else:
		frappe.respond_as_web_page(_("Link Expired"),
			_("Document {0} has been updated by {1}".format(docname, doc.get("modified_by"))),
			indicator_color='blue')


def get_workflow_action_url(action, doctype, docname, current_state):
	apply_action_method = "/api/method/frappe.workflow.doctype.workflow_action.workflow_action.apply_action"

	params = {
		"doctype": doctype,
		"docname": docname,
		"action": action,
		"current_state": current_state
	}

	return get_url(apply_action_method + "?" + get_signed_params(params))