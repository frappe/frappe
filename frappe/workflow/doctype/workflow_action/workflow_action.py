# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.page.permission_manager.permission_manager import get_users_with_role
from frappe.utils.background_jobs import enqueue

class WorkflowAction(Document):
	pass

def has_permission(doc, user):
	if user not in ['Administrator', doc.user]:
		return False

def create_workflow_actions(doc, state):

	from frappe.permissions import has_permission

	workflow = frappe.get_all("Workflow",
		fields=['*'],
		filters=[['document_type', '=', doc.get('doctype')], ['is_active', '=', 1]]
	)

	if not workflow: return

	reference_doctype = doc.doctype
	reference_name = doc.name

	workflow = frappe.get_doc('Workflow', workflow[0].name)

	doc_current_state = doc.get(workflow.workflow_state_field)

	immediate_next_possible_transitions = [d for d in workflow.transitions if d.state == doc_current_state]

	# update status of completed workflow actions
	frappe.db.sql('''update `tabWorkflow Action` set status='Completed', completed_by=%s
		where reference_doctype=%s and reference_name=%s and next_workflow_state=%s''',
		(frappe.session.user, reference_doctype, reference_name, doc_current_state))

	# delete irrelevant workflow actions
	frappe.db.sql('''delete from `tabWorkflow Action`
		where reference_doctype=%s and reference_name=%s and next_workflow_state!=%s''',
		(reference_doctype, reference_name, doc_current_state))

	email_map = {}
	for transition in immediate_next_possible_transitions:
		users = get_users_with_role(transition.allowed)
		for user in users:
			if not has_permission(doctype=doc, user=user): continue

			newdoc = frappe.get_doc({
				'doctype': 'Workflow Action',
				'reference_doctype': reference_doctype,
				'reference_name': reference_name,
				'next_workflow_state': transition.next_state,
				'status': 'Open',
				'action': transition.action,
				'user': user
			})

			if not email_map.get(user):
				email_map[user] = {
					'possible_actions': [],
					'email': frappe.db.get_value('User', user, 'email'),
					'doctype': reference_doctype,
					'docname': reference_name
				}

			email_map[user].get('possible_actions').append({
				'action_name': transition.action,
				'action_link': 'some_link'
			})

			newdoc.insert(ignore_permissions=True)

		send_workflow_action_email(email_map)

	frappe.db.commit()


def send_workflow_action_email(email_map):
	for user, d in email_map.items():
		email_args = {
			'recipients': [d.get('email')],
			'template': 'workflow_action',
			'attachments': [frappe.attach_print(d.get('doctype'), d.get('docname'), file_name=d.get('docname'))],
			'args': {
				'actions': d.get('possible_actions'),
				'message': '{0} {1}'.format(d.get('doctype'), d.get('docname'))
			},
			'header': ["Workflow Action", "orange"]
		}
		enqueue(method=frappe.sendmail, queue='short', timeout=300, async=True, **email_args)

