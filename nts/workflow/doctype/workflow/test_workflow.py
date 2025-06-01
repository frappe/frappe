# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import nts
from nts.model.workflow import (
	WorkflowTransitionError,
	apply_workflow,
	get_common_transition_actions,
)
from nts.query_builder import DocType
from nts.test_runner import make_test_records
from nts.tests.utils import ntsTestCase
from nts.utils import random_string


class TestWorkflow(ntsTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_test_records("User")

	def setUp(self):
		self.patcher = patch("nts.attach_print", return_value={})
		self.patcher.start()
		nts.db.delete("Workflow Action")
		self.workflow = create_todo_workflow()

	def tearDown(self):
		nts.set_user("Administrator")
		self.patcher.stop()
		nts.delete_doc("Workflow", "Test ToDo")

	def test_default_condition(self):
		"""test default condition is set"""
		todo = create_new_todo()

		# default condition is set
		self.assertEqual(todo.workflow_state, "Pending")

		return todo

	def test_approve(self, doc=None):
		"""test simple workflow"""
		todo = doc or self.test_default_condition()

		apply_workflow(todo, "Approve")
		# default condition is set
		self.assertEqual(todo.workflow_state, "Approved")
		self.assertEqual(todo.status, "Closed")

		return todo

	def test_wrong_action(self):
		"""Check illegal action (approve after reject)"""
		todo = self.test_approve()

		self.assertRaises(WorkflowTransitionError, apply_workflow, todo, "Reject")

	def test_workflow_condition(self):
		"""Test condition in transition"""
		self.workflow.transitions[0].condition = 'doc.status == "Closed"'
		self.workflow.save()

		# only approve if status is closed
		self.assertRaises(WorkflowTransitionError, self.test_approve)

		self.workflow.transitions[0].condition = ""
		self.workflow.save()

	def test_get_common_transition_actions(self):
		todo1 = create_new_todo()
		todo2 = create_new_todo()
		todo3 = create_new_todo()
		todo4 = create_new_todo()

		actions = get_common_transition_actions([todo1, todo2, todo3, todo4], "ToDo")
		self.assertSetEqual(set(actions), {"Approve", "Reject"})

		apply_workflow(todo1, "Reject")
		apply_workflow(todo2, "Reject")
		apply_workflow(todo3, "Approve")

		actions = get_common_transition_actions([todo1, todo2, todo3], "ToDo")
		self.assertListEqual(actions, [])

		actions = get_common_transition_actions([todo1, todo2], "ToDo")
		self.assertListEqual(actions, ["Review"])

	def test_if_workflow_actions_were_processed_using_role(self):
		user = nts.get_doc("User", "test2@example.com")
		user.add_roles("Test Approver", "System Manager")
		nts.set_user("test2@example.com")

		doc = self.test_default_condition()
		workflow_actions = nts.get_all("Workflow Action", fields=["*"])
		self.assertEqual(len(workflow_actions), 1)

		# test if status of workflow actions are updated on approval
		self.test_approve(doc)
		user.remove_roles("Test Approver", "System Manager")
		workflow_actions = nts.get_all("Workflow Action", fields=["*"])
		self.assertEqual(len(workflow_actions), 1)
		self.assertEqual(workflow_actions[0].status, "Completed")

	def test_if_workflow_actions_were_processed_using_user(self):
		user = nts.get_doc("User", "test2@example.com")
		user.add_roles("Test Approver", "System Manager")
		nts.set_user("test2@example.com")

		doc = self.test_default_condition()
		workflow_actions = nts.get_all("Workflow Action", fields=["*"])
		self.assertEqual(len(workflow_actions), 1)

		# test if status of workflow actions are updated on approval
		WorkflowAction = DocType("Workflow Action")
		WorkflowActionPermittedRole = DocType("Workflow Action Permitted Role")
		nts.qb.update(WorkflowAction).set(WorkflowAction.user, "test2@example.com").run()
		nts.qb.update(WorkflowActionPermittedRole).set(WorkflowActionPermittedRole.role, "").run()

		self.test_approve(doc)

		user.remove_roles("Test Approver", "System Manager")
		workflow_actions = nts.get_all("Workflow Action", fields=["status"])
		self.assertEqual(len(workflow_actions), 1)
		self.assertEqual(workflow_actions[0].status, "Completed")
		nts.set_user("Administrator")

	def test_if_workflow_set_on_action(self):
		self.workflow._update_state_docstatus = True
		self.workflow.states[1].doc_status = 1
		self.workflow.save()
		todo = create_new_todo()
		self.assertEqual(todo.docstatus, 0)
		todo.submit()
		self.assertEqual(todo.docstatus, 1)
		self.assertEqual(todo.workflow_state, "Approved")

		self.workflow.states[1].doc_status = 0
		self.workflow.save()

	def test_syntax_error_in_transition_rule(self):
		self.workflow.transitions[0].condition = 'doc.status =! "Closed"'

		with self.assertRaises(nts.ValidationError) as se:
			self.workflow.save()

		self.assertTrue(
			"invalid python code" in str(se.exception).lower(), msg="Python code validation not working"
		)


def create_todo_workflow():
	from nts.tests.ui_test_helpers import UI_TEST_USER

	if nts.db.exists("Workflow", "Test ToDo"):
		nts.delete_doc("Workflow", "Test ToDo")

	TEST_ROLE = "Test Approver"

	if not nts.db.exists("Role", TEST_ROLE):
		nts.get_doc(dict(doctype="Role", role_name=TEST_ROLE)).insert(ignore_if_duplicate=True)
		if nts.db.exists("User", UI_TEST_USER):
			nts.get_doc("User", UI_TEST_USER).add_roles(TEST_ROLE)

	workflow = nts.new_doc("Workflow")
	workflow.workflow_name = "Test ToDo"
	workflow.document_type = "ToDo"
	workflow.workflow_state_field = "workflow_state"
	workflow.is_active = 1
	workflow.send_email_alert = 1
	workflow.append("states", dict(state="Pending", allow_edit="All"))
	workflow.append(
		"states",
		dict(state="Approved", allow_edit=TEST_ROLE, update_field="status", update_value="Closed"),
	)
	workflow.append("states", dict(state="Rejected", allow_edit=TEST_ROLE))
	workflow.append(
		"transitions",
		dict(
			state="Pending",
			action="Approve",
			next_state="Approved",
			allowed=TEST_ROLE,
			allow_self_approval=1,
		),
	)
	workflow.append(
		"transitions",
		dict(
			state="Pending",
			action="Reject",
			next_state="Rejected",
			allowed=TEST_ROLE,
			allow_self_approval=1,
		),
	)
	workflow.append(
		"transitions",
		dict(state="Rejected", action="Review", next_state="Pending", allowed="All", allow_self_approval=1),
	)
	workflow.insert(ignore_permissions=True)

	return workflow


def create_new_todo():
	return nts.get_doc(dict(doctype="ToDo", description="workflow " + random_string(10))).insert()
