# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.page.permission_manager.permission_manager import get_users_with_role

class PendingWorkflowAction(Document):
	pass

def create_pending_workflow_actions(doc, state):
	workflow = frappe.get_all("Workflow",
		fields=['*'],
		filters=[['document_type', '=', doc.get('doctype')], ['is_active', '=', 1]]
	)

	reference_doctype = doc.doctype
	reference_name = doc.name

	if workflow:

		workflow = frappe.get_doc('Workflow', workflow[0].name)

		doc_current_state = doc.get(workflow.workflow_state_field)

		immediate_next_possible_transitions = [d for d in workflow.transitions if d.state == doc_current_state]

		for transition in immediate_next_possible_transitions:
			users = get_users_with_role(transition.allowed)
			for user in users:
				newdoc = frappe.get_doc({
					'doctype': 'Pending Workflow Action',
					'reference_doctype': reference_doctype,
					'reference_name': reference_name,
					'workflow_state': transition.state,
					'status': 'Open',
					'user': user
				})
				newdoc.save()

		# update status of old workflow actions
		frappe.db.sql('''update `tabPending Workflow Action` set status='Completed', completed_by=%s
			where reference_doctype=%s and reference_name=%s and workflow_state=%s''',
			(frappe.session.user, reference_doctype, reference_name, doc_current_state))

		frappe.db.commit()

	else: pass

	if(doc.doctype == "Leave Application"):
		frappe.throw('ERROR')

def clear_pending_workflow_actions(doc, state):
	print('---------------clear', doc, state)