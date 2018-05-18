# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.page.permission_manager.permission_manager import get_users_with_role
from frappe.permissions import has_permission

class WorkflowAction(Document):
	pass

def create_workflow_actions(doc, state):
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
		(frappe.session.user, reference_doctype, reference_name, doc_current_state), debug=True)

	# delete irrelevant workflow actions
	frappe.db.sql('''delete from `tabWorkflow Action`
		where reference_doctype=%s and reference_name=%s and next_workflow_state!=%s''',
		(reference_doctype, reference_name, doc_current_state), debug=True)

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
			newdoc.insert(ignore_permissions=True)
			print(newdoc)

	frappe.db.commit()
	# print('--------------------------doc', doc, state, workflow, reference_doctype, reference_name)
	# return

def clear_workflow_actions(doc, state):
	print('---------------clear', doc, state)