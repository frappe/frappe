# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import responses

import frappe
from frappe.model.workflow import (
	WorkflowTransitionError,
	apply_workflow,
	get_common_transition_actions,
	get_transitions,
	get_workflow_name,
	get_workflow_names,
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

	def test_bulk_workflow_approval_accepts_native_list(self):
		from frappe.model.workflow import bulk_workflow_approval

		todo = create_new_todo()
		# docnames as a native list (frappe.parse_json passthrough); < 20 docs runs inline
		bulk_workflow_approval([todo.name], "ToDo", "Approve")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "workflow_state"), "Approved")

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
		dt = create_new_submittable_doctype()
		workflow = create_submittable_workflow(dt.name)
		doc = frappe.get_doc({"doctype": dt.name, "test_field": "test"}).insert()

		workflow._update_state_docstatus = True
		workflow.states[1].doc_status = 1
		workflow.save()

		self.assertEqual(doc.docstatus, 0)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.workflow_state, "Approved")

		workflow.states[1].doc_status = 0
		workflow.save()

	def test_syntax_error_in_transition_rule(self):
		self.workflow.transitions[0].condition = 'doc.status =! "Closed"'

		with self.assertRaises(frappe.ValidationError) as se:
			self.workflow.save()

		self.assertTrue(
			"invalid python code" in str(se.exception).lower(), msg="Python code validation not working"
		)

	def test_dynamic_update_value_expression(self):
		"""Test dynamic expression evaluation in workflow update_value field"""
		self.workflow.states[1].update_field = "assigned_by"
		self.workflow.states[1].update_value = "frappe.session.user"
		self.workflow.states[1].evaluate_as_expression = 1
		self.workflow.save()

		todo = create_new_todo()
		apply_workflow(todo, "Approve")

		self.assertEqual(todo.assigned_by, frappe.session.user)

	def test_dynamic_update_value_with_doc_field(self):
		"""Test dynamic expression using doc field value"""
		self.workflow.states[1].update_field = "description"
		self.workflow.states[1].update_value = "doc.allocated_to or 'No assignee'"
		self.workflow.states[1].evaluate_as_expression = 1
		self.workflow.save()

		todo = create_new_todo()
		todo.allocated_to = "Administrator"
		todo.save()

		apply_workflow(todo, "Approve")

		self.assertEqual(todo.description, "Administrator")

	def test_static_value_when_expression_disabled(self):
		"""Test that value is not evaluated when evaluate_as_expression is disabled"""
		self.workflow.states[1].update_field = "description"
		self.workflow.states[1].update_value = "frappe.session.user"
		self.workflow.states[1].evaluate_as_expression = 0
		self.workflow.save()

		todo = create_new_todo()
		apply_workflow(todo, "Approve")

		self.assertEqual(todo.description, "frappe.session.user")

	def test_invalid_expression_raises_error(self):
		"""Test that invalid expression raises proper error"""
		self.workflow.states[1].update_field = "description"
		self.workflow.states[1].update_value = "invalid_syntax(("
		self.workflow.states[1].evaluate_as_expression = 1
		self.workflow.save()

		todo = create_new_todo()

		with self.assertRaises(frappe.ValidationError):
			apply_workflow(todo, "Approve")

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


def create_new_todo(priority=None):
	todo = frappe.get_doc(doctype="ToDo", description="workflow " + random_string(10))
	if priority:
		todo.priority = priority

	return todo.insert()


def create_new_submittable_doctype():
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


class TestConditionalWorkflow(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_workflow_state_field("ToDo")

	def setUp(self):
		"""Start from a doctype no workflow governs.

		IntegrationTestCase rolls back once the class is done, not between tests, so a workflow
		made by an earlier test is still around. Retiring them here is enough: every workflow gets
		a name of its own, so nothing collides.
		"""
		for name in frappe.get_all("Workflow", {"document_type": "ToDo", "is_active": 1}, pluck="name"):
			frappe.db.set_value("Workflow", name, "is_active", 0)

		frappe.clear_cache(doctype="ToDo")

	def test_conditional_workflow_skips_documents_it_does_not_match(self):
		workflow = create_conditional_todo_workflow(priority="High")

		high = create_new_todo(priority="High")
		self.assertEqual(get_workflow_name("ToDo", high), workflow.name)
		self.assertEqual(high.workflow_state, "Pending")

		low = create_new_todo(priority="Low")
		self.assertIsNone(get_workflow_name("ToDo", low))
		self.assertIsNone(low.workflow_state)
		self.assertEqual(get_transitions(low), [])

	def test_unconditional_workflow_governs_every_document(self):
		workflow = create_conditional_todo_workflow()

		for priority in ("High", "Low"):
			todo = create_new_todo(priority=priority)
			self.assertEqual(get_workflow_name("ToDo", todo), workflow.name)

	def test_highest_priority_matching_workflow_wins(self):
		catch_all = create_conditional_todo_workflow(workflow_priority=0)
		high = create_conditional_todo_workflow(priority="High", workflow_priority=10)

		self.assertEqual(get_workflow_name("ToDo", create_new_todo(priority="High")), high.name)
		self.assertEqual(get_workflow_name("ToDo", create_new_todo(priority="Low")), catch_all.name)

	def test_catch_all_workflow_retires_only_the_other_catch_all(self):
		conditional = create_conditional_todo_workflow(priority="High", workflow_priority=10)
		retired = create_conditional_todo_workflow()
		create_conditional_todo_workflow()

		self.assertEqual(frappe.db.get_value("Workflow", retired.name, "is_active"), 0)
		self.assertEqual(frappe.db.get_value("Workflow", conditional.name, "is_active"), 1)

	def test_moving_between_workflows_re_enters_the_new_one(self):
		create_conditional_todo_workflow(priority="High")
		low = create_conditional_todo_workflow(priority="Low", states=("Rejected", "Approved"))

		todo = create_new_todo(priority="High")
		self.assertEqual(todo.workflow_state, "Pending")

		todo.priority = "Low"
		todo.save()

		self.assertEqual(get_workflow_name("ToDo", todo), low.name)
		self.assertEqual(todo.workflow_state, "Rejected")

	def test_seeding_skips_documents_a_higher_priority_workflow_claims(self):
		todo = create_new_todo(priority="High")
		self.assertIsNone(todo.workflow_state)

		create_conditional_todo_workflow(priority="High", workflow_priority=10)
		create_conditional_todo_workflow(workflow_priority=0)

		todo.reload()
		self.assertEqual(todo.workflow_state, "Pending")

	def test_seeding_at_equal_priority_stays_within_conditions(self):
		todo = create_new_todo(priority="High")
		self.assertIsNone(todo.workflow_state)

		create_conditional_todo_workflow(priority="Low", states=("Rejected", "Approved"))
		high = create_conditional_todo_workflow(priority="High")

		todo.reload()
		self.assertEqual(get_workflow_name("ToDo", todo), high.name)
		self.assertEqual(todo.workflow_state, "Pending")

	def test_deleting_a_workflow_drops_it_from_the_cache(self):
		from frappe.desk.form.meta import get_meta

		workflow = create_conditional_todo_workflow()
		self.assertEqual(get_workflow_names("ToDo"), [workflow.name])

		frappe.delete_doc("Workflow", workflow.name)

		self.assertEqual(get_workflow_names("ToDo"), [])
		self.assertEqual(get_meta("ToDo").get("__workflow_docs"), [])

	def test_desk_metadata_serializes_with_a_workflow(self):
		from frappe.desk.form.load import get_meta_bundle

		create_conditional_todo_workflow()

		workflow_docs = get_meta_bundle("ToDo")[0]["__workflow_docs"]
		self.assertIn("Workflow State", [doc.doctype for doc in workflow_docs])

	def test_conditions_must_name_a_real_field(self):
		workflow = build_todo_workflow()
		workflow.append("conditions", dict(field="not_a_field", condition="=", value="High"))

		self.assertRaises(frappe.ValidationError, workflow.insert)

	def test_active_workflows_must_share_a_state_field(self):
		create_conditional_todo_workflow(priority="High")

		workflow = build_todo_workflow()
		workflow.workflow_state_field = "custom_state"
		workflow.append("conditions", dict(field="priority", condition="=", value="Low"))

		self.assertRaises(frappe.ValidationError, workflow.insert)


def create_workflow_state_field(doctype):
	"""Give the doctype its workflow state field before any test makes a workflow.

	Saving a Workflow creates this field when it is missing, and creating a field is DDL, which
	commits. The workflow saved alongside it would then outlive the test's rollback and resolve
	for every test that follows.
	"""
	if frappe.get_meta(doctype).get_field("workflow_state"):
		return

	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": doctype,
			"fieldname": "workflow_state",
			"label": "Workflow State",
			"fieldtype": "Link",
			"options": "Workflow State",
			"hidden": 1,
			"no_copy": 1,
			"allow_on_submit": 1,
		}
	).insert(ignore_if_duplicate=True)


def build_todo_workflow(states=("Pending", "Approved")):
	workflow = frappe.new_doc("Workflow")
	workflow.workflow_name = f"Test ToDo {frappe.generate_hash(length=8)}"
	workflow.document_type = "ToDo"
	workflow.workflow_state_field = "workflow_state"
	workflow.is_active = 1
	for state in states:
		workflow.append("states", dict(state=state, allow_edit="All"))

	workflow.append(
		"transitions",
		dict(state=states[0], action="Approve", next_state=states[1], allowed="All"),
	)
	return workflow


def create_conditional_todo_workflow(priority=None, workflow_priority=0, states=("Pending", "Approved")):
	workflow = build_todo_workflow(states)
	workflow.priority = workflow_priority
	if priority:
		workflow.append("conditions", dict(field="priority", condition="=", value=priority))

	return workflow.insert()
