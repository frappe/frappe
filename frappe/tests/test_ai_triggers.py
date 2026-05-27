# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import frappe
from frappe.ai.model import ChatResponse, Model
from frappe.ai.tools.builtins import sync_builtin_tools
from frappe.ai.triggers import dispatch, dispatch_scheduled, fire
from frappe.tests import IntegrationTestCase


def _model(**overrides: Any) -> dict:
	doc = {
		"doctype": "AI Model",
		"title": "Triggers Test Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "AI Agent",
		"title": "Triggers Test Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _trigger(agent_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "AI Trigger",
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
		doc = _Bag(doctype="AI Run", name="any")

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
		frappe.db.set_value("AI Trigger", self.trigger.name, "last_fired_at", past, update_modified=False)

		with patch("frappe.enqueue") as enqueue:
			dispatch_scheduled()

		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.kwargs["trigger"], self.trigger.name)

	def test_dispatch_scheduled_skips_when_next_run_in_future(self):
		future = frappe.utils.now_datetime() + timedelta(minutes=5)
		frappe.db.set_value("AI Trigger", self.trigger.name, "last_fired_at", future, update_modified=False)

		with patch("frappe.enqueue") as enqueue:
			dispatch_scheduled()

		enqueue.assert_not_called()

	def test_dispatch_scheduled_updates_last_fired_at(self):
		past = frappe.utils.now_datetime() - timedelta(minutes=5)
		frappe.db.set_value("AI Trigger", self.trigger.name, "last_fired_at", past, update_modified=False)

		with patch("frappe.enqueue"):
			dispatch_scheduled()

		updated = frappe.db.get_value("AI Trigger", self.trigger.name, "last_fired_at")
		self.assertGreater(updated, past)

	def test_dispatch_scheduled_skips_disabled_triggers(self):
		frappe.db.set_value("AI Trigger", self.trigger.name, "enabled", 0)
		past = frappe.utils.now_datetime() - timedelta(minutes=5)
		frappe.db.set_value("AI Trigger", self.trigger.name, "last_fired_at", past, update_modified=False)

		with patch("frappe.enqueue") as enqueue:
			dispatch_scheduled()

		enqueue.assert_not_called()


class TestFire(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

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

		run = frappe.get_doc("AI Run", run_name)
		self.assertEqual(run.source, "Trigger")
		self.assertEqual(run.trigger, self.trigger.name)
		session = frappe.get_doc("AI Session", run.session)
		self.assertEqual(session.agent, self.agent.name)
		self.assertEqual(run.status, "Completed")
		self.assertIn(todo.name, run.input)

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

		run = frappe.get_doc("AI Run", run_name)
		self.assertEqual(run.status, "Completed")
		self.assertEqual(run.trigger, scheduled.name)
