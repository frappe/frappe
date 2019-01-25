# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.utils import get_url, get_datetime
from frappe.desk.form.utils import get_pdf_link
from frappe.utils.verified_command import get_signed_params, verify_request
from frappe import _
from frappe.model.workflow import apply_workflow, get_workflow_name, \
	has_approval_access, get_workflow_state_field, send_email_alert
from frappe.desk.notifications import clear_doctype_notifications

class WorkflowAction(Document):
	pass


def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	if user == "Administrator": return ""

	return "(`tabWorkflow Action`.`user`='{user}')".format(user=user)

def has_permission(doc, user):
	if user not in ['Administrator', doc.user]:
		return False

def process_workflow_actions(doc, state):
	workflow = get_workflow_name(doc.get('doctype'))
	if not workflow: return

	if state == "on_trash":
		clear_workflow_actions(doc.get('doctype'), doc.get('name'))
		return

	if is_workflow_action_already_created(doc): return

	clear_old_workflow_actions(doc)
	update_completed_workflow_actions(doc)
	clear_doctype_notifications('Workflow Action')

	next_possible_transitions = get_next_possible_transitions(workflow, get_doc_workflow_state(doc))

	if not next_possible_transitions: return

	user_data_map = get_users_next_action_data(next_possible_transitions, doc)

	if not user_data_map: return

	create_workflow_actions_for_users(user_data_map.keys(), doc)

	if send_email_alert(workflow):
		enqueue(send_workflow_action_email, queue='short', users_data=list(user_data_map.values()), doc=doc)

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
	if logged_in_user == 'Guest' and user:
		# to allow user to apply action without login
		frappe.set_user(user)

	doc = frappe.get_doc(doctype, docname)
	newdoc = apply_workflow(doc, action)
	frappe.db.commit()
	return_success_page(newdoc)

	# reset session user
	frappe.set_user(logged_in_user)

def return_success_page(doc):
	frappe.respond_as_web_page(_("Success"),
		_("{0}: {1} is set to state {2}".format(
			doc.get('doctype'),
			frappe.bold(doc.get('name')),
			frappe.bold(get_doc_workflow_state(doc))
		)), indicator_color='green')

def return_action_confirmation_page(doc, action, action_link, alert_doc_change=False):
	template_params = {
		'title': doc.get('name'),
		'doctype': doc.get('doctype'),
		'docname': doc.get('name'),
		'action': action,
		'action_link': action_link,
		'alert_doc_change': alert_doc_change
	}

	template_params['pdf_link'] = get_pdf_link(doc.get('doctype'), doc.get('name'))

	frappe.respond_as_web_page(None, None,
		indicator_color="blue",
		template="confirm_workflow_action",
		context=template_params)

def return_link_expired_page(doc, doc_workflow_state):
	frappe.respond_as_web_page(_("Link Expired"),
		_("Document {0} has been set to state {1} by {2}"
			.format(
				frappe.bold(doc.get('name')),
				frappe.bold(doc_workflow_state),
				frappe.bold(frappe.get_value('User', doc.get("modified_by"), 'full_name'))
			)), indicator_color='blue')

def clear_old_workflow_actions(doc, user=None):
	user = user if user else frappe.session.user
	frappe.db.sql("""DELETE FROM `tabWorkflow Action`
		WHERE `reference_doctype`=%s AND `reference_name`=%s AND `user`!=%s AND `status`='Open'""",
		(doc.get('doctype'), doc.get('name'), user))

def update_completed_workflow_actions(doc, user=None):
	user = user if user else frappe.session.user
	frappe.db.sql("""UPDATE `tabWorkflow Action` SET `status`='Completed', `completed_by`=%s
		WHERE `reference_doctype`=%s AND `reference_name`=%s AND `user`=%s AND `status`='Open'""",
		(user, doc.get('doctype'), doc.get('name'), user))

def get_next_possible_transitions(workflow_name, state):
	return frappe.get_all('Workflow Transition',
		fields=['allowed', 'action', 'state', 'allow_self_approval'],
		filters=[['parent', '=', workflow_name],
		['state', '=', state]])

def get_users_next_action_data(transitions, doc):
	user_data_map = {}
	for transition in transitions:
		users = get_users_with_role(transition.allowed)
		filtered_users = filter_allowed_users(users, doc, transition)
		for user in filtered_users:
			if not user_data_map.get(user):
				user_data_map[user] = {
					'possible_actions': [],
					'email': frappe.db.get_value('User', user, 'email'),
				}

			user_data_map[user].get('possible_actions').append({
				'action_name': transition.action,
				'action_link': get_workflow_action_url(transition.action, doc, user)
			})
	return user_data_map


def create_workflow_actions_for_users(users, doc):
	for user in users:
		frappe.get_doc({
			'doctype': 'Workflow Action',
			'reference_doctype': doc.get('doctype'),
			'reference_name': doc.get('name'),
			'workflow_state': get_doc_workflow_state(doc),
			'status': 'Open',
			'user': user
		}).insert(ignore_permissions=True)

	frappe.db.commit()


def send_workflow_action_email(users_data, doc):
	common_args = get_common_email_args(doc)
	message = common_args.pop('message', None)
	for d in users_data:
		email_args = {
			'recipients': [d.get('email')],
			'args': {
				'actions': d.get('possible_actions'),
				'message': message
			},
		}
		email_args.update(common_args)
		enqueue(method=frappe.sendmail, queue='short', **email_args)

def get_workflow_action_url(action, doc, user):
	apply_action_method = "/api/method/frappe.workflow.doctype.workflow_action.workflow_action.apply_action"

	params = {
		"doctype": doc.get('doctype'),
		"docname": doc.get('name'),
		"action": action,
		"current_state": get_doc_workflow_state(doc),
		"user": user,
		"last_modified": doc.get('modified')
	}

	return get_url(apply_action_method + "?" + get_signed_params(params))

def get_confirm_workflow_action_url(doc, action, user):
	confirm_action_method = "/api/method/frappe.workflow.doctype.workflow_action.workflow_action.confirm_action"

	params = {
		"action": action,
		"doctype": doc.get('doctype'),
		"docname": doc.get('name'),
		"user": user
	}

	return get_url(confirm_action_method + "?" + get_signed_params(params))


def get_users_with_role(role):
	return [p[0] for p in frappe.db.sql("""SELECT DISTINCT `tabUser`.`name`
		FROM `tabHas Role`, `tabUser`
		WHERE `tabHas Role`.`role`=%s
		AND `tabUser`.`name`!='Administrator'
		AND `tabHas Role`.`parent`=`tabUser`.`name`
		AND `tabUser`.`enabled`=1""", role)]

def is_workflow_action_already_created(doc):
	return frappe.db.exists({
		'doctype': 'Workflow Action',
		'reference_doctype': doc.get('doctype'),
		'reference_name': doc.get('name'),
		'workflow_state': get_doc_workflow_state(doc)
	})

def clear_workflow_actions(doctype, name):
	if not (doctype and name):
		return

	frappe.db.sql('''delete from `tabWorkflow Action`
		where reference_doctype=%s and reference_name=%s''',
		(doctype, name))

def get_doc_workflow_state(doc):
	workflow_name = get_workflow_name(doc.get('doctype'))
	workflow_state_field = get_workflow_state_field(workflow_name)
	return doc.get(workflow_state_field)

def filter_allowed_users(users, doc, transition):
	"""Filters list of users by checking if user has access to doc and
	if the user satisfies 'workflow transision self approval' condition
	"""
	from frappe.permissions import has_permission
	filtered_users = []
	for user in users:
		if (has_approval_access(user, doc, transition)
			and has_permission(doctype=doc, user=user)):
			filtered_users.append(user)
	return filtered_users

def get_common_email_args(doc):
	doctype = doc.get('doctype')
	docname = doc.get('name')

	email_template = get_email_template(doc)
	if email_template:
		subject = frappe.render_template(email_template.subject, vars(doc))
		response = frappe.render_template(email_template.response, vars(doc))
	else:
		subject = _('Workflow Action')
		response = _('{0}: {1}'.format(doctype, docname))

	common_args = {
		'template': 'workflow_action',
		'attachments': [frappe.attach_print(doctype, docname , file_name=docname)],
		'subject': subject,
		'message': response
	}
	return common_args

def get_email_template(doc):
	"""Returns next_action_email_template
	for workflow state (if available) based on doc current workflow state
	"""
	workflow_name = get_workflow_name(doc.get('doctype'))
	doc_state = get_doc_workflow_state(doc)
	template_name = frappe.db.get_value('Workflow Document State', {
		'parent': workflow_name,
		'state': doc_state
	}, 'next_action_email_template')

	if not template_name: return
	return frappe.get_doc('Email Template', template_name)

