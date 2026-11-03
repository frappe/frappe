# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.model.workflow import (
	WorkflowTransitionError,
	apply_workflow,
	get_common_transition_actions,
	get_workflow_name,
)
from frappe.query_builder import DocType
from frappe.test_runner import make_test_records
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string


class TestWorkflow(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_test_records("User")

	def setUp(self):
		self.patcher = patch("frappe.attach_print", return_value={})
		self.patcher.start()
		frappe.db.delete("Workflow Action")
		self.workflow = create_todo_workflow()

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

	def test_deleting_workflow_clears_cached_name(self):
		"""A deleted workflow must not stay cached against its document type"""
		self.assertEqual(get_workflow_name("ToDo"), "Test ToDo")

		frappe.delete_doc("Workflow", "Test ToDo")

		self.assertFalse(get_workflow_name("ToDo"))
		create_new_todo()

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

	def test_if_workflow_actions_were_processed_using_user(self):
		user = frappe.get_doc("User", "test2@example.com")
		user.add_roles("Test Approver", "System Manager")
		frappe.set_user("test2@example.com")

		doc = self.test_default_condition()
		workflow_actions = frappe.get_all("Workflow Action", fields=["*"])
		self.assertEqual(len(workflow_actions), 1)

		# test if status of workflow actions are updated on approval
		WorkflowAction = DocType("Workflow Action")
		WorkflowActionPermittedRole = DocType("Workflow Action Permitted Role")
		frappe.qb.update(WorkflowAction).set(WorkflowAction.user, "test2@example.com").run()
		frappe.qb.update(WorkflowActionPermittedRole).set(WorkflowActionPermittedRole.role, "").run()

		self.test_approve(doc)

		user.remove_roles("Test Approver", "System Manager")
		workflow_actions = frappe.get_all("Workflow Action", fields=["status"])
		self.assertEqual(len(workflow_actions), 1)
		self.assertEqual(workflow_actions[0].status, "Completed")
		frappe.set_user("Administrator")

	def add_approver(self):
		"""Give the workflow a mail recipient other than the document owner."""
		user = frappe.get_doc("User", "test2@example.com")
		user.add_roles("Test Approver", "System Manager")
		self.addCleanup(user.remove_roles, "Test Approver", "System Manager")

	def test_workflow_action_recreated_when_state_is_re_entered(self):
		"""A document coming back to a state it already left needs a fresh action and notification."""
		self.add_approver()

		def open_states():
			return frappe.get_all(
				"Workflow Action",
				filters={"reference_doctype": "ToDo", "reference_name": todo.name, "status": "Open"},
				pluck="workflow_state",
			)

		with patch("frappe.sendmail") as sendmail:
			todo = create_new_todo()
			self.assertEqual(open_states(), ["Pending"])
			self.assertTrue(sendmail.called)

			apply_workflow(todo, "Reject")
			self.assertEqual(open_states(), ["Rejected"])

			sendmail.reset_mock()
			apply_workflow(todo, "Review")
			self.assertEqual(open_states(), ["Pending"])
			self.assertTrue(sendmail.called)

		actions = frappe.get_all(
			"Workflow Action",
			filters={"reference_doctype": "ToDo", "reference_name": todo.name, "workflow_state": "Pending"},
			pluck="status",
			order_by="creation asc",
		)
		self.assertEqual(actions, ["Completed", "Open"])

	def test_workflow_action_not_duplicated_on_resave(self):
		"""Saving without leaving the state must not create another action or resend the email."""
		self.add_approver()

		with patch("frappe.sendmail") as sendmail:
			todo = create_new_todo()
			sendmail.reset_mock()

			todo.description = "edited " + random_string(10)
			todo.save()

			self.assertFalse(sendmail.called)

		actions = frappe.get_all(
			"Workflow Action", filters={"reference_doctype": "ToDo", "reference_name": todo.name}
		)
		self.assertEqual(len(actions), 1)

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

	def test_queued_workflow_action_returns_doc(self):
		dt = create_new_submittable_doctype()
		workflow = create_submittable_workflow(dt.name)
		workflow._update_state_docstatus = True
		workflow.states[1].doc_status = 1
		workflow.save()
		doc = frappe.get_doc({"doctype": dt.name, "test_field": "test"}).insert()

		with (
			patch.object(doc.meta, "queue_in_background", 1),
			patch("frappe.utils.scheduler.is_scheduler_inactive", return_value=False),
		):
			queued_doc = apply_workflow(doc, "Approve")

		self.assertEqual(queued_doc.name, doc.name)
		self.assertEqual(queued_doc.workflow_state, "Approved")
		self.assertTrue(
			frappe.db.exists("Submission Queue", {"ref_doctype": dt.name, "ref_docname": doc.name})
		)

	def test_syntax_error_in_transition_rule(self):
		self.workflow.transitions[0].condition = 'doc.status =! "Closed"'

		with self.assertRaises(frappe.ValidationError) as se:
			self.workflow.save()

		self.assertTrue(
			"invalid python code" in str(se.exception).lower(), msg="Python code validation not working"
		)


def create_todo_workflow():
	from frappe.tests.ui_test_helpers import UI_TEST_USER

	if frappe.db.exists("Workflow", "Test ToDo"):
		frappe.delete_doc("Workflow", "Test ToDo")

	TEST_ROLE = "Test Approver"

	if not frappe.db.exists("Role", TEST_ROLE):
		frappe.get_doc(dict(doctype="Role", role_name=TEST_ROLE)).insert(ignore_if_duplicate=True)
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


def create_new_todo():
	return frappe.get_doc(dict(doctype="ToDo", description="workflow " + random_string(10))).insert()


def create_new_submittable_doctype():
	if frappe.db.exists("DocType", "Test Submittable Doc"):
		return frappe.get_doc("DocType", "Test Submittable Doc")

	return frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"name": "Test Submittable Doc",
			"custom": 1,
			"is_submittable": 1,
			"fields": [
				{"label": "Field", "fieldname": "test_field", "fieldtype": "Data"},
				{
					"label": "Workflow State",
					"fieldname": "workflow_state",
					"fieldtype": "Link",
					"options": "Workflow State",
				},
			],
			"permissions": [{"role": "System Manager", "read": 1, "write": 1, "submit": 1, "cancel": 1}],
		}
	).insert(ignore_if_duplicate=True)


def create_submittable_workflow(doctype):
	if frappe.db.exists("Workflow", "Submittable Workflow"):
		return frappe.get_doc("Workflow", "Submittable Workflow")

	workflow = frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": "Submittable Workflow",
			"document_type": doctype,
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"states": [
				{"state": "Pending", "allow_edit": "All"},
				{"state": "Approved", "allow_edit": "System Manager", "doc_status": 0},
			],
			"transitions": [
				{
					"state": "Pending",
					"action": "Approve",
					"next_state": "Approved",
					"allowed": "System Manager",
					"allow_self_approval": 1,
				}
			],
		}
	).insert(ignore_permissions=True, ignore_if_duplicate=True)

	return workflow


class TestWorkflowFieldLevelRead(FrappeTestCase):
	def setUp(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype
		from frappe.core.doctype.user.user import generate_keys

		frappe.set_user("Administrator")
		self.user = "workflow.fieldlevel@example.com"
		if not frappe.db.exists("User", self.user):
			frappe.get_doc(
				doctype="User",
				email=self.user,
				first_name="Workflow Field Level",
				roles=[{"role": "Desk User"}],
				send_welcome_email=0,
			).insert()
		keys = generate_keys(self.user)
		self.headers = {"Authorization": f"token {keys['api_key']}:{keys['api_secret']}"}

		self.doctype = (
			new_doctype(
				fields=[
					{"fieldname": "title", "fieldtype": "Data", "label": "Title"},
					{
						"fieldname": "secret",
						"fieldtype": "Data",
						"label": "Secret",
						"permlevel": 1,
						"default": "hidden",
					},
					{
						"fieldname": "workflow_state",
						"fieldtype": "Link",
						"label": "Workflow State",
						"options": "Workflow State",
						"permlevel": 1,
					},
				],
				permissions=[
					{"role": "Desk User", "read": 1, "write": 1, "create": 1, "permlevel": 0},
					{"role": "Desk User", "read": 0, "write": 1, "permlevel": 1},
				],
			)
			.insert()
			.name
		)
		self.workflow = frappe.get_doc(
			{
				"doctype": "Workflow",
				"workflow_name": f"Field Level {self.doctype}",
				"document_type": self.doctype,
				"workflow_state_field": "workflow_state",
				"is_active": 1,
				"states": [
					{"state": "Pending", "allow_edit": "All"},
					{"state": "Approved", "allow_edit": "All", "doc_status": 0},
				],
				"transitions": [
					{
						"state": "Pending",
						"action": "Approve",
						"next_state": "Approved",
						"allowed": "Desk User",
						"allow_self_approval": 1,
					}
				],
			}
		).insert()
		self.name = frappe.get_doc(doctype=self.doctype, title="x").insert().name
		frappe.db.commit()  # nosemgrep

	def tearDown(self):
		try:
			frappe.set_user("Administrator")
			for action in frappe.get_all(
				"Workflow Action", {"reference_doctype": self.doctype}, pluck="name"
			):
				frappe.delete_doc("Workflow Action", action, force=True)
			frappe.delete_doc("Workflow", self.workflow.name, force=True)
			frappe.delete_doc("DocType", self.doctype, force=True)
			frappe.delete_doc_if_exists("User", self.user)
			frappe.db.commit()  # nosemgrep
		finally:
			super().tearDown()

	def test_whitelisted_apply_workflow_omits_unreadable_fields(self):
		from frappe.tests.test_api import make_request
		from frappe.utils import get_test_client

		response = make_request(
			get_test_client(use_cookies=False).post,
			args=("/api/method/frappe.model.workflow.apply_workflow",),
			kwargs={
				"json": {"doc": frappe.get_doc(self.doctype, self.name).as_json(), "action": "Approve"},
				"headers": self.headers,
			},
			site=frappe.local.site,
		)
		self.assertEqual(response.status_code, 200, response.text)
		doc = response.json["message"]
		self.assertEqual(doc["title"], "x")
		self.assertIsNone(doc.get("secret"))
		self.assertIsNone(doc.get("workflow_state"))

	def test_confirm_action_page_sees_workflow_state_of_unreadable_field(self):
		from frappe.workflow.doctype.workflow_action import workflow_action

		frappe.set_user(self.user)
		with (
			patch.object(workflow_action, "verify_request", return_value=True),
			patch.object(workflow_action, "return_success_page") as page,
		):
			workflow_action.confirm_action(self.doctype, self.name, self.user, "Approve")

		self.assertEqual(page.call_args.args[0].workflow_state, "Approved")
