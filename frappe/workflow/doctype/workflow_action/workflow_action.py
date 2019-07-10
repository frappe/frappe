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
from frappe.model.workflow import apply_workflow, get_workflow, get_transitions,\
	has_approval_access, get_workflow_state_field, send_email_alert
from frappe.desk.notifications import clear_doctype_notifications
from frappe.utils.user import get_users_with_role

class WorkflowAction(Document):
	pass


def on_doctype_update():
	frappe.db.add_index("Workflow Action", ["status", "user"])

def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	if user == "Administrator": return ""

	return "(`tabWorkflow Action`.`user`='{user}')".format(user=user)

def has_permission(doc, user):
	if user not in ['Administrator', doc.user]:
		return False

def process_workflow_actions(doc, state):
	workflow = get_workflow(doc)
	if not workflow: return

	if state == "on_trash":
		clear_workflow_actions(doc.get('doctype'), doc.get('name'))
		return

	if is_workflow_action_already_created(doc): return

	clear_old_workflow_actions(doc)
	update_completed_workflow_actions(doc)
	clear_doctype_notifications('Workflow Action')
	create_workflow_actions(workflow, doc)

def create_workflow_actions(workflow, doc, user = None, possible_actions=None, action_source=None,
	previous_user=None, comment=None):
	next_possible_transitions = get_transitions(doc)

	if not next_possible_transitions:
		current_state = doc.get(workflow.workflow_state_field)
		user = user or frappe.session.user
		if hasattr(doc,'workflow_action') and doc.workflow_action == 'Reject':
			user = doc.owner
		if user == doc.owner and current_state == workflow.states[0].state:
			next_possible_transitions = [frappe._dict({'action':'Start', 'is_approve':0,
				'name':'', 'allow_self_approval':1})]
		else:
			email_args = {'recipients': [d.get('owner')],
				'subject': 'Workflow %s %s finished' %(doc.doctype,doc.name)
			}
			enqueue(method=frappe.sendmail, queue='short', **email_args )
			return

	user_data_map = get_users_next_action_data(next_possible_transitions, doc, user)

	if not user_data_map:
		frappe.throw(_('Can not determine next user per workflow definion'))
		return

	create_workflow_actions_for_users(user_data_map, doc, actions=possible_actions,
		action_source= action_source, previous_user=previous_user, comment=comment)

	if send_email_alert(workflow.name):
		enqueue(send_workflow_action_email, queue='short', users_data=list(user_data_map.values()), doc=doc)

@frappe.whitelist(allow_guest=True)
def apply_action(action, doctype, docname, current_state, user=None, last_modified=None,transition=None):
	if not verify_request():
		return

	doc = frappe.get_doc(doctype, docname)
	doc_workflow_state = get_doc_workflow_state(doc)

	if doc_workflow_state == current_state:
		action_link = get_confirm_workflow_action_url(doc, action, user, transition)

		if not last_modified or get_datetime(doc.modified) == get_datetime(last_modified):
			return_action_confirmation_page(doc, action, action_link)
		else:
			return_action_confirmation_page(doc, action, action_link, alert_doc_change=True)

	else:
		return_link_expired_page(doc, doc_workflow_state)

@frappe.whitelist(allow_guest=True)
def confirm_action(doctype, docname, user, action, transition):
	if not verify_request():
		return

	logged_in_user = frappe.session.user
	if logged_in_user == 'Guest' and user:
		# to allow user to apply action without login
		frappe.set_user(user)

	doc = frappe.get_doc(doctype, docname)
	newdoc = apply_workflow(doc, action,transition_name=transition)
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

def update_completed_workflow_actions(doc, user=None, action=None):
	user = user if user else frappe.session.user
	frappe.db.sql("""UPDATE `tabWorkflow Action` SET `status`='Completed', `completed_by`=%s, actions=%s
		WHERE `reference_doctype`=%s AND `reference_name`=%s AND `user`=%s AND `status`='Open'""",
		(user, action or doc.get('workflow_action'), doc.get('doctype'), doc.get('name'), user))

def get_users_next_action_data(transitions, doc, user =None):
	"""for Forward and Add Additional Check, user is directly provided"""

	user_data_map = {}
	if user:
		users = [user]
	for transition in transitions:
		if not user	:
			if transition.assign_user_mode =='User From Doc Field':
				if '.' in transition.doc_field:
					parent_field, sub_field = transition.doc_field.split('.')
					users = [child.get(sub_field) for child in doc.get(parent_field)]
				else:
					user = doc.get(transition.doc_field)
					if not user:
						continue
					else:
						users = doc.get(transition.doc_field).split(';')
			elif  transition.assign_user_mode == 'User From Workflow':
				users = transition.user.split(';')
			elif transition.assign_user_mode in ['Role From Doc Field','Role From Workflow']:
				role = doc.get(transition.doc_field) if transition.assign_user_mode == 'Role From Doc Field' else transition.allowed
				users = get_users_with_role(role)
		#users = get_users_with_role(transition.allowed)
		filtered_users = filter_allowed_users(list(set(users)), doc, transition)
		for user in filtered_users:
			if not user_data_map.get(user):
				user_data_map[user] = {
					'possible_actions': [],
					'email': frappe.db.get_value('User', user, 'email'),
				}

			user_data_map[user].get('possible_actions').append({
				'allow_self_approval': transition.allow_self_approval,
				'transition':  transition.name,
				'action_name': transition.action,
				'action_link': get_workflow_action_url(transition.action, doc, user,transition.name)
			})
			if transition.is_approve:
				user_data_map[user].get('possible_actions').append({
					'allow_self_approval': transition.allow_self_approval,
					'transition':  transition.name,
					'action_name': 'Reject',
					'action_link': get_workflow_action_url('Reject', doc, user,transition.name)
				})

	return user_data_map


def create_workflow_actions_for_users(users, doc, actions=None, action_source=None, previous_user=None, comment=None):
	def get_delegate(delegate_type, user):
		cur_time = datetime.datetime.now()
		filters={'type':delegate_type,
		              'delegator': user,
		              'valid_from': ('<', cur_time), 'valid_to': ('>', cur_time),
		              'active':1}
		delegatee = frappe.get_list('Delegation', filters = filters,fields='delegatee',
						ignore_permissions=True, as_list=1)
		if delegatee:
			return delegatee[0][0]
	for user, v in users.items():
		if not user:
			continue
		agent = get_delegate('Pre-Check', user)
		if agent:
			previous_user , action_source, user = user, 'Pre-Check', agent
		else:	# when pre-check exist, do not check delegation anymore
			agent = get_delegate('Delegate', user)
			if agent:
				previous_user, action_source, user = user, 'Delegate', agent
		actions = actions or ';'.join(['%s:%s:%s' %(i['action_name'],i['transition'],i['allow_self_approval'])
						 for i in v['possible_actions']])
		frappe.get_doc({
			'doctype': 'Workflow Action',
			'reference_doctype': doc.get('doctype'),
			'reference_name': doc.get('name'),
			'workflow_state': get_doc_workflow_state(doc),
			'status': 'Open',
			'user': user,
			'actions': actions,
			'previous_user': previous_user,
			'action_source' : action_source,
			'comment': comment or doc.get('workflow_comment')
		}).insert(ignore_permissions=True)

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
			'reference_name': doc.name,
			'reference_doctype': doc.doctype
		}
		email_args.update(common_args)
		enqueue(method=frappe.sendmail, queue='short', **email_args)

def get_workflow_action_url(action, doc, user, transition):
	apply_action_method = "/api/method/frappe.workflow.doctype.workflow_action.workflow_action.apply_action"

	params = {
		"doctype": doc.get('doctype'),
		"docname": doc.get('name'),
		"action": action,
		"current_state": get_doc_workflow_state(doc),
		"user": user,
		"last_modified": doc.get('modified'),
		"transition": transition
	}

	return get_url(apply_action_method + "?" + get_signed_params(params))

def get_confirm_workflow_action_url(doc, action, user, transition=None):
	confirm_action_method = "/api/method/frappe.workflow.doctype.workflow_action.workflow_action.confirm_action"

	params = {
		"action": action,
		"doctype": doc.get('doctype'),
		"docname": doc.get('name'),
		"user": user,
		"transition":transition
	}

	return get_url(confirm_action_method + "?" + get_signed_params(params))

def is_workflow_action_already_created(doc):
	return frappe.db.exists({
		'doctype': 'Workflow Action',
		'reference_doctype': doc.get('doctype'),
		'reference_name': doc.get('name'),
		'workflow_state': get_doc_workflow_state(doc),
		'status':'Open'
	})

def clear_workflow_actions(doctype, name):
	if not (doctype and name):
		return

	frappe.db.sql('''delete from `tabWorkflow Action`
		where reference_doctype=%s and reference_name=%s''',
		(doctype, name))

def get_doc_workflow_state(doc):
	workflow = get_workflow(doc)
	if not workflow:
		return
	workflow_state_field = get_workflow_state_field(workflow.name)
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

		response = _('{0}: {1}'.format(doctype, docname))
		subject = '% required for %s' %(_('Workflow Action'), response)
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
	workflow = get_workflow(doc.get('doctype'))
	if not workflow:
		return
	doc_state = get_doc_workflow_state(doc)
	template_name = frappe.db.get_value('Workflow Document State', {
		'parent': workflow.name,
		'state': doc_state
	}, 'next_action_email_template')

	if not template_name: return
	return frappe.get_doc('Email Template', template_name)

def get_state_optional_field_value(workflow_name, state):
	return frappe.get_cached_value('Workflow Document State', {
		'parent': workflow_name,
		'state': state
	}, 'is_state_optional')
