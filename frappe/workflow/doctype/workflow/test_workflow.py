# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import responses

import frappe
from frappe.model.workflow import (
	WorkflowTransitionError,
	apply_workflow,
	get_common_transition_actions,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import make_test_records
from frappe.utils import random_string


class TestWorkflow(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_test_records("User")
		cls.enterClassContext(cls.enable_safe_exec())

	def setUp(self):
		self.patcher = patch("frappe.attach_print", return_value={})
		self.patcher.start()
		frappe.db.delete("Workflow Action")
		self.workflow = create_todo_workflow()
		create_domain_workflow()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.patcher.stop()

		frappe.delete_doc("Workflow", "Test ToDo")

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
		user = frappe.get_doc("User", "test2@example.com")
		user.add_roles("Test Approver", "System Manager")
		frappe.set_user("test2@example.com")

		doc = self.test_default_condition()
		workflow_actions = frappe.get_all("Workflow Action", fields=["*"])
		self.assertEqual(len(workflow_actions), 1)

		# test if status of workflow actions are updated on approval
		self.test_approve(doc)
		user.remove_roles("Test Approver", "System Manager")
		workflow_actions = frappe.get_all("Workflow Action", fields=["*"])
		self.assertEqual(len(workflow_actions), 1)
		self.assertEqual(workflow_actions[0].status, "Completed")

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

		with self.assertRaises(frappe.ValidationError) as se:
			self.workflow.save()

		self.assertTrue(
			"invalid python code" in str(se.exception).lower(), msg="Python code validation not working"
		)

	# app-defined workflow task tests start here
	def test_sync_tasks(self, doc=None):
		"""test workflow with workflow tasks (server scripts, webhooks and app-defined methods)"""

		# for webhooks
		self.responses = responses.RequestsMock()
		self.responses.start()

		self.responses.add(
			responses.POST,
			"https://workflowtasks.org/post",
			status=200,
			json={},
		)

		domain = frappe.new_doc("Domain")
		domain.domain = random_string(length=10)
		domain.save()

		with self.patch_hooks(
			{
				"workflow_methods": [
					{
						"name": "Create Note",
						"method": "frappe.workflow.doctype.workflow.test_workflow.create_new_note",
					}
				]
			}
		):
			apply_workflow(domain, "Approve")

		# refer create_new_task()
		self.assertTrue(
			frappe.db.exists("Note", {"title": "workflow - " + domain.name, "content": "workflow test"})
		)
		self.assertTrue(frappe.db.exists("Domain", {"name": "workflow - " + domain.name}))
		self.assertTrue(frappe.db.exists("Webhook Request Log", {"url": "https://workflowtasks.org/post"}))

		# for webhooks
		self.responses.stop()
		self.responses.reset()

		return domain


def create_todo_workflow():
	from frappe.tests.ui_test_helpers import UI_TEST_USER

	if frappe.db.exists("Workflow", "Test ToDo"):
		frappe.delete_doc("Workflow", "Test ToDo")

	TEST_ROLE = "Test Approver"

	if not frappe.db.exists("Role", TEST_ROLE):
		frappe.get_doc(doctype="Role", role_name=TEST_ROLE).insert(ignore_if_duplicate=True)
		if frappe.db.exists("User", UI_TEST_USER):
			frappe.get_doc("User", UI_TEST_USER).add_roles(TEST_ROLE)

	workflow = frappe.new_doc("Workflow")
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


def create_domain_workflow():
	from frappe.tests.ui_test_helpers import UI_TEST_USER

	if frappe.db.exists("Workflow", "Test Domain"):
		frappe.delete_doc("Workflow", "Test Domain")

	TEST_ROLE = "Test Approver"

	if not frappe.db.exists("Role", TEST_ROLE):
		frappe.get_doc(doctype="Role", role_name=TEST_ROLE).insert(ignore_if_duplicate=True)
		if frappe.db.exists("User", UI_TEST_USER):
			frappe.get_doc("User", UI_TEST_USER).add_roles(TEST_ROLE)

	server_script = create_new_server_script()
	webhook = create_new_webhook()

	pending_to_approved_transition = frappe.new_doc("Workflow Transition Tasks")
	pending_to_approved_transition.name = random_string(length=10)
	pending_to_approved_transition.append("tasks", {"task": "Create Note"})
	pending_to_approved_transition.append("tasks", {"task": "Server Script", "link": server_script.name})
	pending_to_approved_transition.append("tasks", {"task": "Webhook", "link": webhook.name})

	pending_to_approved_transition.save()

	workflow = frappe.new_doc("Workflow")
	workflow.workflow_name = "Test Domain"
	workflow.document_type = "Domain"
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
			transition_tasks=pending_to_approved_transition.name,
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
	return frappe.get_doc(doctype="ToDo", description="workflow " + random_string(10)).insert()


def create_new_note(doc):
	note = frappe.new_doc("Note")
	note.title = "workflow - " + doc.name
	note.content = "workflow test"

	note.save()


def create_new_server_script():
	server_script = frappe.new_doc("Server Script")
	server_script.name = random_string(length=10)
	server_script.script_type = "Workflow Task"
	server_script.script = """
# create a domain with the same name as the given document
domain = frappe.new_doc("Domain")
domain.domain = "workflow - " + doc.name

domain.save()
	"""
	server_script.save()

	return server_script


def create_new_webhook():
	webhook = frappe.new_doc("Webhook")
	webhook.__newname = random_string(10)
	webhook.webhook_docevent = "workflow_transition"
	webhook.webhook_doctype = "Domain"
	webhook.request_method = "POST"
	webhook.request_url = "https://workflowtasks.org/post"
	webhook.save()

	return webhook
