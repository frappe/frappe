# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.utils import random_string
from frappe.model.workflow import apply_workflow, WorkflowTransitionError, WorkflowPermissionError, get_common_transition_actions
from frappe.test_runner import make_test_records


class TestWorkflow(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		make_test_records("User")

	def setUp(self):
		self.workflow = create_todo_workflow()
		frappe.set_user('Administrator')

	def tearDown(self):
		frappe.delete_doc('Workflow', 'Test ToDo')

	def test_default_condition(self):
		'''test default condition is set'''
		todo = create_new_todo()

		# default condition is set
		self.assertEqual(todo.workflow_state, 'Pending')

		return todo

	def test_approve(self, doc=None):
		'''test simple workflow'''
		todo = doc or self.test_default_condition()

		apply_workflow(todo, 'Approve')
		# default condition is set
		self.assertEqual(todo.workflow_state, 'Approved')
		self.assertEqual(todo.status, 'Closed')

		return todo

	def test_wrong_action(self):
		'''Check illegal action (approve after reject)'''
		todo = self.test_approve()

		self.assertRaises(WorkflowTransitionError, apply_workflow, todo, 'Reject')

	def test_workflow_condition(self):
		'''Test condition in transition'''
		self.workflow.transitions[0].condition = 'doc.status == "Closed"'
		self.workflow.save()

		# only approve if status is closed
		self.assertRaises(WorkflowTransitionError, self.test_approve)

		self.workflow.transitions[0].condition = ''
		self.workflow.save()

	def test_get_common_transition_actions(self):
		todo1 = create_new_todo()
		todo2 = create_new_todo()
		todo3 = create_new_todo()
		todo4 = create_new_todo()

		actions = get_common_transition_actions([todo1, todo2, todo3, todo4], 'ToDo')
		self.assertSetEqual(set(actions), set(['Approve', 'Reject']))

		apply_workflow(todo1, 'Reject')
		apply_workflow(todo2, 'Reject')
		apply_workflow(todo3, 'Approve')

		actions = get_common_transition_actions([todo1, todo2, todo3], 'ToDo')
		self.assertListEqual(actions, [])

		actions = get_common_transition_actions([todo1, todo2], 'ToDo')
		self.assertListEqual(actions, ['Review'])

	def test_if_workflow_actions_were_processed(self):
		frappe.db.sql('delete from `tabWorkflow Action`')
		user = frappe.get_doc('User', 'test2@example.com')
		user.add_roles('Test Approver', 'System Manager')
		frappe.set_user('test2@example.com')

		doc = self.test_default_condition()
		workflow_actions = frappe.get_all('Workflow Action', fields=['*'])
		self.assertEqual(len(workflow_actions), 1)

		# test if status of workflow actions are updated on approval
		self.test_approve(doc)
		user.remove_roles('Test Approver', 'System Manager')
		workflow_actions = frappe.get_all('Workflow Action', fields=['status'])
		self.assertEqual(len(workflow_actions), 1)
		self.assertEqual(workflow_actions[0].status, 'Completed')
		frappe.set_user('Administrator')

	def test_update_docstatus(self):
		todo = create_new_todo()
		apply_workflow(todo, 'Approve')

		self.workflow.states[1].doc_status = 0
		self.workflow.save()
		todo.reload()
		self.assertEqual(todo.docstatus, 0)
		self.workflow.states[1].doc_status = 1
		self.workflow.save()
		todo.reload()
		self.assertEqual(todo.docstatus, 1)

		self.workflow.states[1].doc_status = 0
		self.workflow.save()

	def test_if_workflow_set_on_action(self):
		self.workflow.states[1].doc_status = 1
		self.workflow.save()
		todo = create_new_todo()
		self.assertEqual(todo.docstatus, 0)
		todo.submit()
		self.assertEqual(todo.docstatus, 1)
		self.assertEqual(todo.workflow_state, 'Approved')

		self.workflow.states[1].doc_status = 0
		self.workflow.save()

def create_todo_workflow():
	if frappe.db.exists('Workflow', 'Test ToDo'):
		frappe.delete_doc('Workflow', 'Test ToDo')

	if not frappe.db.exists('Role', 'Test Approver'):
		frappe.get_doc(dict(doctype='Role',
			role_name='Test Approver')).insert(ignore_if_duplicate=True)
	workflow = frappe.new_doc('Workflow')
	workflow.workflow_name = 'Test ToDo'
	workflow.document_type = 'ToDo'
	workflow.workflow_state_field = 'workflow_state'
	workflow.is_active = 1
	workflow.send_email_alert = 0
	workflow.append('states', dict(
		state = 'Pending', allow_edit = 'All'
	))
	workflow.append('states', dict(
		state = 'Approved', allow_edit = 'Test Approver',
		update_field = 'status', update_value = 'Closed'
	))
	workflow.append('states', dict(
		state = 'Rejected', allow_edit = 'Test Approver'
	))
	workflow.append('transitions', dict(
		state = 'Pending', action='Approve', next_state = 'Approved',
		allowed='Test Approver', allow_self_approval= 1
	))
	workflow.append('transitions', dict(
		state = 'Pending', action='Reject', next_state = 'Rejected',
		allowed='Test Approver', allow_self_approval= 1
	))
	workflow.append('transitions', dict(
		state = 'Rejected', action='Review', next_state = 'Pending',
		allowed='All', allow_self_approval= 1
	))
	workflow.insert(ignore_permissions=True)

	return workflow

def create_new_todo():
	return frappe.get_doc(dict(doctype='ToDo', description='workflow ' + random_string(10))).insert()
