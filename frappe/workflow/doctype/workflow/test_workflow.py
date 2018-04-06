# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.utils import random_string
from frappe.model.workflow import apply_workflow, WorkflowTransitionError

class TestWorkflow(unittest.TestCase):
	def setUp(self):
		if not getattr(self, 'workflow', None):
			frappe.get_doc(dict(doctype='Role',
				role_name='Test Approver')).insert(ignore_if_duplicate=True)

			if frappe.db.exists('Workflow', 'Test ToDo'):
				self.workflow = frappe.get_doc('Workflow', 'Test ToDo')
			else:
				self.workflow = frappe.new_doc('Workflow')
				self.workflow.workflow_name = 'Test ToDo'
				self.workflow.document_type = 'ToDo'
				self.workflow.is_active = 1
				self.workflow.append('states', dict(
					state = 'Pending', allow_edit = 'All'
				))
				self.workflow.append('states', dict(
					state = 'Approved', allow_edit = 'Test Approver'
				))
				self.workflow.append('states', dict(
					state = 'Rejected', allow_edit = 'Test Approver'
				))
				self.workflow.append('transitions', dict(
					state = 'Pending', action='Approve', next_state = 'Approved', allowed='Test Approver'
				))
				self.workflow.append('transitions', dict(
					state = 'Pending', action='Reject', next_state = 'Rejected', allowed='Test Approver'
				))
				self.workflow.append('transitions', dict(
					state = 'Rejected', action='Review', next_state = 'Pending', allowed='All'
				))
				self.workflow.insert()

	def test_default_condition(self):
		todo = frappe.get_doc(dict(doctype='ToDo', description='workflow ' + random_string(10))).insert()

		# default condition is set
		self.assertEqual(todo.workflow_state, 'Pending')

		return todo

	def test_approve(self):
		todo = self.test_default_condition()

		apply_workflow(todo, 'Approve')

		# default condition is set
		self.assertEqual(todo.workflow_state, 'Approved')

		return todo

	def test_wrong_action(self):
		todo = self.test_approve()

		self.assertRaises(WorkflowTransitionError, apply_workflow, todo, 'Reject')
