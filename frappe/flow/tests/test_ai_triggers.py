# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.lib.model import ChatResponse, Model
from flow.tools.builtins import sync_builtin_tools
from flow.triggers import dispatch, dispatch_scheduled, fire


def _model(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Model",
		"title": "Triggers Test Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Agent",
		"title": "Triggers Test Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _trigger(agent_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Trigger",
		"title": "Triggers Test Trigger",
		"agent": agent_name,
		"enabled": 1,
		"event": "DocType Event",
		"target_doctype": "ToDo",
		"doc_event": "after_insert",
		"prompt_template": "New {{ doc.doctype }} {{ doc.name }}",
	}
	doc.update(overrides)
	return doc


def _final(text: str = "ok") -> ChatResponse:
	return ChatResponse(
		content=text,
		finish_reason="stop",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


class _Bag:
	"""Tiny test helper: a doc-shaped object with arbitrary attrs."""

	def __init__(self, **attrs: Any) -> None:
		self.__dict__.update(attrs)


class TestDispatch(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()
		cls.enterClassContext(cls.enable_safe_exec())

	def setUp(self):
		self.model = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model.name)).insert()
		self.trigger = frappe.get_doc(_trigger(self.agent.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_dispatch_enqueues_matching_trigger(self):
		doc = _Bag(doctype="ToDo", name="todo-x")

		with patch("frappe.enqueue") as enqueue:
			dispatch(doc, "after_insert")

		enqueue.assert_called_once()
		kwargs = enqueue.call_args.kwargs
		self.assertEqual(kwargs["trigger"], self.trigger.name)
		self.assertEqual(kwargs["target_doctype"], "ToDo")
		self.assertEqual(kwargs["target_name"], "todo-x")
		self.assertTrue(kwargs["enqueue_after_commit"])

	def test_dispatch_ignores_unknown_method(self):
		doc = _Bag(doctype="ToDo", name="todo-x")

		with patch("frappe.enqueue") as enqueue:
			dispatch(doc, "before_save")

		enqueue.assert_not_called()

	def test_dispatch_ignores_ai_doctypes(self):
		doc = _Bag(doctype="Flow Run", name="any")

		with patch("frappe.enqueue") as enqueue:
			dispatch(doc, "after_insert")

		enqueue.assert_not_called()

	def test_dispatch_skips_when_event_mismatched(self):
		doc = _Bag(doctype="ToDo", name="todo-x")

		with patch("frappe.enqueue") as enqueue:
			dispatch(doc, "on_submit")

		enqueue.assert_not_called()

	def test_dispatch_skips_when_doctype_mismatched(self):
		doc = _Bag(doctype="User", name="someone@example.com")

		with patch("frappe.enqueue") as enqueue:
			dispatch(doc, "after_insert")

		enqueue.assert_not_called()

	def test_dispatch_evaluates_condition(self):
		self.trigger.condition = "doc.status == 'Closed'"
		self.trigger.save()
		open_doc = frappe.get_doc({"doctype": "ToDo", "description": "open one"}).insert()
		closed_doc = frappe.get_doc(
			{"doctype": "ToDo", "description": "closed one", "status": "Closed"}
		).insert()

		with patch("frappe.enqueue") as enqueue:
			dispatch(open_doc, "after_insert")
		enqueue.assert_not_called()

		with patch("frappe.enqueue") as enqueue:
			dispatch(closed_doc, "after_insert")
		enqueue.assert_called_once()

	def test_dispatch_evaluates_multiline_condition(self):
		self.trigger.condition = (
			"status = frappe.db.get_value('ToDo', doc.name, 'status')\nresult = status == 'Closed'"
		)
		self.trigger.save()
		open_doc = frappe.get_doc({"doctype": "ToDo", "description": "open one"}).insert()
		closed_doc = frappe.get_doc(
			{"doctype": "ToDo", "description": "closed one", "status": "Closed"}
		).insert()

		with patch("frappe.enqueue") as enqueue:
			dispatch(open_doc, "after_insert")
		enqueue.assert_not_called()

		with patch("frappe.enqueue") as enqueue:
			dispatch(closed_doc, "after_insert")
		enqueue.assert_called_once()

	def test_dispatch_evaluates_condition_as_run_as(self):
		# The pre-enqueue check runs as run_as, not the triggering user.
		service = frappe.get_doc(
			{
				"doctype": "User",
				"email": "dispatch-service@example.com",
				"first_name": "Svc",
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		self.trigger.run_as = service.name
		self.trigger.condition = f"frappe.session.user == '{service.name}'"
		self.trigger.save()
		doc = frappe.get_doc({"doctype": "ToDo", "description": "run-as cond"}).insert()

		with patch("frappe.enqueue") as enqueue:
			dispatch(doc, "after_insert")

		enqueue.assert_called_once()
		self.assertEqual(frappe.session.user, "Administrator")  # restored afterward

	def test_condition_runtime_error_skips_trigger(self):
		self.trigger.condition = "doc.status.no_such_method()"
		self.trigger.save()
		doc = frappe.get_doc({"doctype": "ToDo", "description": "boom"}).insert()

		with patch("frappe.enqueue") as enqueue:
			dispatch(doc, "after_insert")

		enqueue.assert_not_called()

	def test_condition_script_without_result_rejected_on_save(self):
		self.trigger.condition = "status = doc.status"
		with self.assertRaisesRegex(frappe.ValidationError, "result"):
			self.trigger.save()

	def test_disabled_trigger_does_not_dispatch(self):
		self.trigger.enabled = 0
		self.trigger.save()
		doc = _Bag(doctype="ToDo", name="todo-x")

		with patch("frappe.enqueue") as enqueue:
			dispatch(doc, "after_insert")

		enqueue.assert_not_called()


class TestDispatchScheduled(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model.name)).insert()
		self.trigger = frappe.get_doc(
			_trigger(
				self.agent.name,
				event="Scheduled",
				target_doctype=None,
				doc_event=None,
				cron_expression="* * * * *",
				prompt_template="run",
			)
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_dispatch_scheduled_fires_overdue_trigger(self):
		past = frappe.utils.now_datetime() - timedelta(minutes=5)
		frappe.db.set_value("Flow Trigger", self.trigger.name, "last_fired_at", past, update_modified=False)

		with patch("frappe.enqueue") as enqueue:
			dispatch_scheduled()

		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.kwargs["trigger"], self.trigger.name)

	def test_dispatch_scheduled_skips_when_next_run_in_future(self):
		future = frappe.utils.now_datetime() + timedelta(minutes=5)
		frappe.db.set_value("Flow Trigger", self.trigger.name, "last_fired_at", future, update_modified=False)

		with patch("frappe.enqueue") as enqueue:
			dispatch_scheduled()

		enqueue.assert_not_called()

	def test_dispatch_scheduled_updates_last_fired_at(self):
		past = frappe.utils.now_datetime() - timedelta(minutes=5)
		frappe.db.set_value("Flow Trigger", self.trigger.name, "last_fired_at", past, update_modified=False)

		with patch("frappe.enqueue"):
			dispatch_scheduled()

		updated = frappe.db.get_value("Flow Trigger", self.trigger.name, "last_fired_at")
		self.assertGreater(updated, past)

	def test_dispatch_scheduled_skips_disabled_triggers(self):
		frappe.db.set_value("Flow Trigger", self.trigger.name, "enabled", 0)
		past = frappe.utils.now_datetime() - timedelta(minutes=5)
		frappe.db.set_value("Flow Trigger", self.trigger.name, "last_fired_at", past, update_modified=False)

		with patch("frappe.enqueue") as enqueue:
			dispatch_scheduled()

		enqueue.assert_not_called()


class TestFire(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()
		cls.enterClassContext(cls.enable_safe_exec())

	def setUp(self):
		self.model = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model.name)).insert()
		self.trigger = frappe.get_doc(_trigger(self.agent.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_fire_runs_agent_and_links_trigger(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "fire test"}).insert()

		with patch.object(Model, "chat", return_value=_final("done")):
			run_name = fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)

		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.source, "Trigger")
		self.assertEqual(run.trigger, self.trigger.name)
		session = frappe.get_doc("Flow Session", run.session)
		self.assertEqual(session.agent, self.agent.name)
		self.assertEqual(run.status, "Completed")
		self.assertIn(todo.name, run.input)
		self.assertEqual(run.reference_doctype, "ToDo")
		self.assertEqual(run.reference_name, todo.name)

	def test_fire_runs_as_trigger_owner_not_triggering_user(self):
		# Helpdesk scenario: a low-privilege user (no Flow Agent access) fires the trigger by
		# creating a doc; the agent must still run, with the owner's authority.
		owner = frappe.get_doc(
			{
				"doctype": "User",
				"email": "trigger-owner@example.com",
				"first_name": "Owner",
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		customer = frappe.get_doc(
			{"doctype": "User", "email": "trigger-customer@example.com", "first_name": "Cust"}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Flow Trigger", self.trigger.name, "owner", owner.name)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "help me"}).insert()

		frappe.set_user(customer.name)
		try:
			with patch.object(Model, "chat", return_value=_final("done")):
				run_name = fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)
		finally:
			frappe.set_user("Administrator")

		self.assertIsNotNone(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.owner, owner.name)
		self.assertEqual(frappe.get_doc("Flow Session", run.session).owner, owner.name)

	def test_fire_runs_as_configured_run_as_user(self):
		# run_as overrides the owner: the agent runs with that user's scope.
		service_user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "trigger-service@example.com",
				"first_name": "Service",
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		self.trigger.run_as = service_user.name
		self.trigger.save()
		todo = frappe.get_doc({"doctype": "ToDo", "description": "run-as"}).insert()

		with patch.object(Model, "chat", return_value=_final("done")):
			run_name = fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)

		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.owner, service_user.name)
		self.assertEqual(run.status, "Completed")

	def test_run_as_disabled_user_rejected(self):
		disabled = frappe.get_doc(
			{"doctype": "User", "email": "trigger-disabled@example.com", "first_name": "Off", "enabled": 0}
		).insert(ignore_permissions=True)
		self.trigger.run_as = disabled.name
		with self.assertRaisesRegex(frappe.ValidationError, "Run As must be an enabled user"):
			self.trigger.save()

	def test_fire_restores_the_original_user(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "restore"}).insert()
		with patch.object(Model, "chat", return_value=_final("done")):
			fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)
		self.assertEqual(frappe.session.user, "Administrator")

	def _execute_then_final(self):
		from flow.lib.model import ToolCall

		return [
			ChatResponse(
				content=None,
				tool_calls=[ToolCall(id="c1", name="execute", arguments={"code": "result = 1"})],
				finish_reason="tool_calls",
			),
			_final("done"),
		]

	def test_fire_auto_approves_confirmation_tools_when_enabled(self):
		# auto_approve trigger: the requires_confirmation tool (execute) runs unattended
		# instead of parking the run in Paused.
		self.trigger.auto_approve = 1
		self.trigger.save()
		todo = frappe.get_doc({"doctype": "ToDo", "description": "auto-approve"}).insert()

		with patch.object(Model, "chat", side_effect=self._execute_then_final()):
			run_name = fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)

		self.assertEqual(frappe.get_doc("Flow Run", run_name).status, "Completed")

	def test_fire_pauses_on_confirmation_tool_without_auto_approve(self):
		# Default trigger (auto_approve off): a confirmation tool still pauses for approval.
		todo = frappe.get_doc({"doctype": "ToDo", "description": "needs approval"}).insert()

		with patch.object(Model, "chat", side_effect=self._execute_then_final()):
			run_name = fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)

		self.assertEqual(frappe.get_doc("Flow Run", run_name).status, "Paused")

	def test_fire_skips_disabled_trigger(self):
		self.trigger.enabled = 0
		self.trigger.save()
		todo = frappe.get_doc({"doctype": "ToDo", "description": "skip"}).insert()

		with patch.object(Model, "chat", return_value=_final("done")) as chat:
			run_name = fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)

		self.assertIsNone(run_name)
		chat.assert_not_called()

	def test_fire_skips_when_target_missing(self):
		with patch.object(Model, "chat", return_value=_final("done")) as chat:
			run_name = fire(self.trigger.name, target_doctype="ToDo", target_name="does-not-exist")

		self.assertIsNone(run_name)
		chat.assert_not_called()

	def test_fire_rechecks_condition_after_load(self):
		self.trigger.condition = "doc.status == 'Closed'"
		self.trigger.save()
		todo = frappe.get_doc({"doctype": "ToDo", "description": "open", "status": "Open"}).insert()

		with patch.object(Model, "chat", return_value=_final("done")) as chat:
			run_name = fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)

		self.assertIsNone(run_name)
		chat.assert_not_called()

	def test_fire_scheduled_trigger_without_target(self):
		scheduled = frappe.get_doc(
			_trigger(
				self.agent.name,
				title="Scheduled Trigger Test",
				event="Scheduled",
				target_doctype=None,
				doc_event=None,
				cron_expression="0 9 * * 5",
				prompt_template="weekly run at {{ now }}",
			)
		).insert()

		with patch.object(Model, "chat", return_value=_final("done")):
			run_name = fire(scheduled.name)

		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.trigger, scheduled.name)
		self.assertIsNone(run.reference_doctype)
		self.assertIsNone(run.reference_name)
