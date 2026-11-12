# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.api import bulk, bulk_actions
from frappe.api.utils import FrappeValueError
from frappe.tests import IntegrationTestCase
from frappe.workflow.doctype.workflow.test_workflow import (
	create_new_submittable_doctype,
	create_submittable_workflow,
	create_todo_workflow,
	create_workflow_state_field,
)

PREFIX = "bulk47063"
SUBMITTABLE = "Test Submittable Doc"
USER = "bulk47063@example.com"


class TestBulkSubmitCancelWorkflow(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_workflow_state_field("ToDo")
		if not frappe.db.exists("DocType", SUBMITTABLE):
			create_new_submittable_doctype()
			frappe.db.commit()  # nosemgrep
			cls.addClassCleanup(cls.drop_submittable_doctype)

	@staticmethod
	def drop_submittable_doctype():
		frappe.delete_doc("DocType", SUBMITTABLE, force=True)
		frappe.db.commit()  # nosemgrep

	def setUp(self):
		self.addCleanup(self.cleanup)
		self.addCleanup(frappe.set_user, "Administrator")
		patcher = patch("frappe.attach_print", return_value={})
		patcher.start()
		self.addCleanup(patcher.stop)
		frappe.form_dict.clear()
		self.docs = [self.make_doc(i) for i in range(3)]

	def cleanup(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for name in frappe.get_all(SUBMITTABLE, {"test_field": ["like", f"{PREFIX}%"]}, pluck="name"):
			doc = frappe.get_doc(SUBMITTABLE, name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc(SUBMITTABLE, name, force=True)
		for name in frappe.get_all("ToDo", {"description": ["like", f"{PREFIX}%"]}, pluck="name"):
			frappe.delete_doc("ToDo", name, force=True)
		frappe.delete_doc_if_exists("Workflow", "Submittable Workflow")
		frappe.delete_doc_if_exists("Workflow", "Test ToDo")
		frappe.db.commit()  # nosemgrep

	def make_doc(self, index: int, doctype: str = SUBMITTABLE, submit: bool = False) -> str:
		field = "test_field" if doctype == SUBMITTABLE else "description"
		doc = frappe.get_doc({"doctype": doctype, field: f"{PREFIX} {index}"}).insert()
		if submit:
			doc.submit()
		return doc.name

	def docstatuses(self, names=None) -> list[int]:
		return [frappe.db.get_value(SUBMITTABLE, name, "docstatus") for name in names or self.docs]

	def post(self, route, doctype=SUBMITTABLE, names=None, **body):
		frappe.form_dict.clear()
		frappe.form_dict.update(names=self.docs if names is None else names, **body)
		return getattr(bulk_actions, route)(doctype)

	def make_user(self, gate: int = 1) -> str:
		if not frappe.db.exists("User", USER):
			user = frappe.get_doc(
				{"doctype": "User", "email": USER, "first_name": "Bulk", "send_welcome_email": 0}
			).insert()
			user.add_roles("Desk User")
		frappe.db.set_value("User", USER, "bulk_actions", gate)
		frappe.clear_document_cache("User", USER)
		return USER

	# Submit and cancel

	def test_submit_submits_every_record(self):
		result = self.post("bulk_submit_docs")
		self.assertCountEqual(result["done"], self.docs)
		self.assertEqual(result["failed"], [])
		self.assertEqual(self.docstatuses(), [1, 1, 1])

	def test_submit_fails_a_submitted_record_alone(self):
		submitted = self.make_doc(9, submit=True)
		result = self.post("bulk_submit_docs", names=[*self.docs, submitted])
		self.assertCountEqual(result["done"], self.docs)
		self.assertEqual([failure["name"] for failure in result["failed"]], [submitted])
		self.assertIn("docstatus", result["failed"][0]["error"])

	def test_cancel_cancels_every_submitted_record(self):
		names = [self.make_doc(i, submit=True) for i in range(10, 12)]
		result = self.post("bulk_cancel_docs", names=names)
		self.assertCountEqual(result["done"], names)
		self.assertEqual(self.docstatuses(names), [2, 2])

	def test_cancel_fails_a_draft_alone(self):
		submitted = self.make_doc(10, submit=True)
		result = self.post("bulk_cancel_docs", names=[submitted, self.docs[0]])
		self.assertEqual(result["done"], [submitted])
		self.assertEqual([failure["name"] for failure in result["failed"]], [self.docs[0]])
		self.assertEqual(self.docstatuses(self.docs[:1]), [0])

	def test_submit_by_filters_takes_what_the_list_shows(self):
		frappe.form_dict.clear()
		frappe.form_dict.filters = [["test_field", "like", f"{PREFIX}%"]]
		result = bulk_actions.bulk_submit_docs(SUBMITTABLE)
		self.assertCountEqual(result["done"], self.docs)

	def test_cancel_by_filters_takes_what_the_list_shows(self):
		names = [self.make_doc(i, submit=True) for i in range(10, 12)]
		frappe.form_dict.clear()
		frappe.form_dict.filters = [["test_field", "like", f"{PREFIX} 1_"]]
		result = bulk_actions.bulk_cancel_docs(SUBMITTABLE)
		self.assertCountEqual(result["done"], names)
		self.assertEqual(self.docstatuses(names), [2, 2])

	def test_submit_checks_the_submit_permission_of_each_record(self):
		frappe.set_user(self.make_user())
		result = self.post("bulk_submit_docs")
		self.assertEqual(result["done"], [])
		self.assertEqual(len(result["failed"]), 3)
		self.assertEqual(self.docstatuses(), [0, 0, 0])

	def test_submit_reports_queued_records_as_queued(self):
		with (
			patch.object(frappe.get_meta(SUBMITTABLE), "queue_in_background", 1),
			patch("frappe.api.bulk_actions.is_scheduler_inactive", return_value=False),
			patch("frappe.api.bulk_actions.queue_submission") as queue,
		):
			result = self.post("bulk_submit_docs")

		self.assertCountEqual(result["queued"], self.docs)
		self.assertEqual(result["done"], [])
		self.assertEqual(queue.call_count, 3)
		self.assertEqual(queue.call_args.args[1], "Submit")
		self.assertFalse(queue.call_args.kwargs["alert"])
		self.assertEqual(self.docstatuses(), [0, 0, 0])

	def test_cancel_goes_through_the_queue_too(self):
		submitted = self.make_doc(10, submit=True)
		with (
			patch.object(frappe.get_meta(SUBMITTABLE), "queue_in_background", 1),
			patch("frappe.api.bulk_actions.is_scheduler_inactive", return_value=False),
			patch("frappe.api.bulk_actions.queue_submission") as queue,
		):
			result = self.post("bulk_cancel_docs", names=[submitted])

		self.assertEqual(result["queued"], [submitted])
		self.assertEqual(queue.call_args.args[1], "Cancel")

	def test_inactive_scheduler_submits_in_place(self):
		with (
			patch.object(frappe.get_meta(SUBMITTABLE), "queue_in_background", 1),
			patch("frappe.api.bulk_actions.is_scheduler_inactive", return_value=True),
		):
			result = self.post("bulk_submit_docs")

		self.assertCountEqual(result["done"], self.docs)
		self.assertEqual(self.docstatuses(), [1, 1, 1])
		self.assertEqual(frappe.message_log, [])

	def test_background_run_submits_by_the_action_path(self):
		result = bulk.run_task(
			bulk_actions.SUBMIT.path, [[SUBMITTABLE, name] for name in self.docs], [], {}, False
		)
		self.assertCountEqual(result["done"], self.docs)
		self.assertEqual(self.docstatuses(), [1, 1, 1])

	def test_submit_and_cancel_are_refused_on_a_workflow_doctype(self):
		create_submittable_workflow(SUBMITTABLE)
		for route in ("bulk_submit_docs", "bulk_cancel_docs"):
			with self.assertRaises(frappe.ValidationError):
				self.post(route)
		self.assertEqual(self.docstatuses(), [0, 0, 0])

	def test_submit_is_refused_on_a_doctype_that_is_not_submittable(self):
		todo = self.make_doc(0, "ToDo")
		with self.assertRaises(frappe.ValidationError):
			self.post("bulk_submit_docs", "ToDo", names=[todo])

	def test_the_gate_refuses_submit_cancel_and_workflow(self):
		frappe.set_user(self.make_user(gate=0))
		for route in ("bulk_submit_docs", "bulk_cancel_docs", "bulk_workflow_docs", "bulk_workflow_actions"):
			with self.assertRaises(frappe.PermissionError):
				self.post(route, action="Approve")
		self.assertEqual(self.docstatuses(), [0, 0, 0])

	# Workflow

	def make_todos(self, count: int = 3) -> list[str]:
		create_todo_workflow()
		return [self.make_doc(i, "ToDo") for i in range(count)]

	def states(self, todos: list[str]) -> list[str]:
		return [frappe.db.get_value("ToDo", name, "workflow_state") for name in todos]

	def test_workflow_applies_the_transition_to_every_record(self):
		todos = self.make_todos()
		result = self.post("bulk_workflow_docs", "ToDo", names=todos, action="Approve")
		self.assertCountEqual(result["done"], todos)
		self.assertEqual(self.states(todos), ["Approved"] * 3)

	def test_workflow_by_filters_applies_the_transition_to_what_the_list_shows(self):
		todos = self.make_todos()
		frappe.form_dict.clear()
		frappe.form_dict.update(filters=[["description", "like", f"{PREFIX}%"]], action="Approve")
		result = bulk_actions.bulk_workflow_docs("ToDo")
		self.assertCountEqual(result["done"], todos)
		self.assertEqual(self.states(todos), ["Approved"] * 3)

	def test_workflow_fails_a_record_the_transition_does_not_apply_to_alone(self):
		todos = self.make_todos()
		self.post("bulk_workflow_docs", "ToDo", names=todos[:1], action="Approve")
		result = self.post("bulk_workflow_docs", "ToDo", names=todos, action="Approve")
		self.assertCountEqual(result["done"], todos[1:])
		self.assertEqual([failure["name"] for failure in result["failed"]], todos[:1])
		self.assertIn("Not a valid Workflow Action", result["failed"][0]["error"])

	def test_workflow_needs_an_action(self):
		todos = self.make_todos(1)
		for action in (None, "", ["Approve"]):
			with self.assertRaises(FrappeValueError):
				self.post("bulk_workflow_docs", "ToDo", names=todos, action=action)

	def test_workflow_is_refused_on_a_doctype_without_one(self):
		todo = self.make_doc(0, "ToDo")
		with self.assertRaises(frappe.ValidationError):
			self.post("bulk_workflow_docs", "ToDo", names=[todo], action="Approve")

	def test_workflow_runs_the_transition_roles_check_per_record(self):
		todos = self.make_todos(2)
		frappe.set_user(self.make_user())
		result = self.post("bulk_workflow_docs", "ToDo", names=todos, action="Approve")
		self.assertEqual(result["done"], [])
		self.assertEqual(len(result["failed"]), 2)

	def test_workflow_reports_a_transition_queued_for_submission_as_queued(self):
		frappe.get_doc(
			{
				"doctype": "Workflow",
				"workflow_name": "Submittable Workflow",
				"document_type": SUBMITTABLE,
				"workflow_state_field": "workflow_state",
				"is_active": 1,
				"states": [
					{"state": "Pending", "allow_edit": "All", "doc_status": 0},
					{"state": "Approved", "allow_edit": "All", "doc_status": 1},
				],
				"transitions": [
					{"state": "Pending", "action": "Approve", "next_state": "Approved", "allowed": "All"}
				],
			}
		).insert(ignore_permissions=True)
		with (
			patch.object(frappe.get_meta(SUBMITTABLE), "queue_in_background", 1),
			patch("frappe.utils.scheduler.is_scheduler_inactive", return_value=False),
			patch("frappe.model.document.Document.queue_action"),
		):
			result = self.post("bulk_workflow_docs", names=self.docs, action="Approve")

		self.assertCountEqual(result["queued"], self.docs)
		self.assertEqual(result["done"], [])
		self.assertEqual(self.docstatuses(), [0, 0, 0])
		self.assertEqual(frappe.message_log, [])

	# Common transitions

	def test_common_actions_are_those_every_record_allows(self):
		todos = self.make_todos(2)
		actions = self.post("bulk_workflow_actions", "ToDo", names=todos)
		self.assertCountEqual(actions, ["Approve", "Reject"])

		self.post("bulk_workflow_docs", "ToDo", names=todos[:1], action="Reject")
		self.assertEqual(self.post("bulk_workflow_actions", "ToDo", names=todos[:1]), ["Review"])
		self.assertEqual(self.post("bulk_workflow_actions", "ToDo", names=todos), [])

	def test_common_actions_are_empty_when_a_record_has_no_workflow_state(self):
		todos = self.make_todos(2)
		frappe.db.set_value("ToDo", todos[1], "workflow_state", None)
		self.assertEqual(self.post("bulk_workflow_actions", "ToDo", names=todos), [])

	def test_common_actions_refuse_a_malformed_name(self):
		todos = self.make_todos(1)
		with self.assertRaises(FrappeValueError):
			self.post("bulk_workflow_actions", "ToDo", names=[*todos, {"x": 1}])

	def test_common_actions_by_filters(self):
		self.make_todos(2)
		frappe.form_dict.clear()
		frappe.form_dict.filters = [["description", "like", f"{PREFIX}%"]]
		self.assertCountEqual(bulk_actions.bulk_workflow_actions("ToDo"), ["Approve", "Reject"])

	def test_common_actions_by_dict_filters(self):
		self.make_todos(2)
		frappe.form_dict.clear()
		frappe.form_dict.filters = {"description": ["like", f"{PREFIX}%"]}
		self.assertCountEqual(bulk_actions.bulk_workflow_actions("ToDo"), ["Approve", "Reject"])

	def test_common_actions_are_refused_on_a_doctype_without_a_workflow(self):
		todo = self.make_doc(0, "ToDo")
		with self.assertRaises(frappe.ValidationError):
			self.post("bulk_workflow_actions", "ToDo", names=[todo])

	def test_common_actions_respect_the_cap(self):
		todos = self.make_todos(2)
		with patch.dict(frappe.conf, {"bulk_operation_limit": 1}):
			with self.assertRaises(frappe.ValidationError):
				self.post("bulk_workflow_actions", "ToDo", names=todos)
