# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import frappe
from frappe.flow.daemon.client import DaemonClient
from frappe.flow.permissions import FLOW_USER_ROLE
from frappe.flow.tests.test_fake_daemon import FakeDaemon
from frappe.flow.tools.builtins import sync_builtin_tools
from frappe.flow.triggers import dispatch, dispatch_scheduled, fire
from frappe.tests import IntegrationTestCase


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


def _user(email: str, *roles: str) -> str:
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in roles],
		}
	).insert(ignore_permissions=True)
	return email


class _Bag:
	"""Tiny test helper: a doc-shaped object with arbitrary attrs."""

	def __init__(self, **attrs: Any) -> None:
		self.__dict__.update(attrs)


class TestDispatch(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()
		cls.enterClassContext(patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True))

	def setUp(self):
		self.model = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model.name)).insert()
		self.trigger = frappe.get_doc(_trigger(self.agent.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_dispatch_enqueues_matching_triggers_only(self):
		with patch("frappe.enqueue") as enqueue:
			dispatch(_Bag(doctype="ToDo", name="todo-x"), "after_insert")
		enqueue.assert_called_once_with(
			"frappe.flow.triggers.fire",
			enqueue_after_commit=True,
			trigger=self.trigger.name,
			target_doctype="ToDo",
			target_name="todo-x",
			deleted_doc=None,
		)
		with self.assertQueryCount(0), patch("frappe.enqueue") as enqueue:
			dispatch(_Bag(doctype="ToDo", name="todo-x"), "after_insert")  # from the cache
		enqueue.assert_called_once()

		for doctype, method in (
			("ToDo", "before_save"),  # not a doc event
			("ToDo", "on_submit"),  # another event
			("User", "after_insert"),  # another DocType
			("Flow Run", "after_insert"),  # Flow's own DocTypes
		):
			with self.subTest(doctype=doctype, method=method), patch("frappe.enqueue") as enqueue:
				dispatch(_Bag(doctype=doctype, name="x"), method)
				enqueue.assert_not_called()

		self.trigger.enabled = 0
		self.trigger.save()
		with patch("frappe.enqueue") as enqueue:
			dispatch(_Bag(doctype="ToDo", name="todo-x"), "after_insert")
		enqueue.assert_not_called()

		frappe.get_doc(_trigger(self.agent.name, title="Second Triggers Test Trigger")).insert()
		with patch("frappe.enqueue") as enqueue:
			dispatch(_Bag(doctype="ToDo", name="todo-x"), "after_insert")
		enqueue.assert_called_once()

		frappe.db.rollback()  # neither trigger was committed
		with patch("frappe.enqueue") as enqueue:
			dispatch(_Bag(doctype="ToDo", name="todo-x"), "after_insert")
		enqueue.assert_not_called()

	def test_dispatch_checks_the_condition_as_the_run_as_user(self):
		open_doc = frappe.get_doc({"doctype": "ToDo", "description": "open one"}).insert()
		closed_doc = frappe.get_doc(
			{"doctype": "ToDo", "description": "closed one", "status": "Closed"}
		).insert()
		script = "status = frappe.db.get_value('ToDo', doc.name, 'status')\nresult = status == 'Closed'"
		for condition, doc, fires in (
			("doc.status == 'Closed'", open_doc, False),
			("doc.status == 'Closed'", closed_doc, True),
			(script, open_doc, False),
			(script, closed_doc, True),
			("doc.status.no_such_method()", closed_doc, False),  # a failing condition skips
		):
			with self.subTest(condition=condition, status=doc.status):
				self.trigger.condition = condition
				self.trigger.save()
				with patch("frappe.enqueue") as enqueue, patch("frappe.log_error"):
					dispatch(doc, "after_insert")
				self.assertEqual(enqueue.call_count, int(fires))

		# checked as run_as, not as the user whose change fired it
		self.trigger.run_as = _user("dispatch-service@example.com", "System Manager", FLOW_USER_ROLE)
		self.trigger.condition = f"frappe.session.user == '{self.trigger.run_as}'"
		self.trigger.save()
		with patch("frappe.enqueue") as enqueue:
			dispatch(closed_doc, "after_insert")
		enqueue.assert_called_once()
		self.assertEqual(frappe.session.user, "Administrator")  # restored afterward


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

	def test_dispatch_scheduled_fires_triggers_that_are_due(self):
		now = frappe.utils.now_datetime()
		past = now - timedelta(minutes=5)
		for case, values, fires in (
			("overdue", {"last_fired_at": past}, True),
			(
				"never fired, due since creation",
				{"last_fired_at": None, "creation": now - timedelta(hours=2)},
				True,
			),
			("next run ahead", {"last_fired_at": now + timedelta(minutes=5)}, False),
			("disabled", {"last_fired_at": past, "enabled": 0}, False),
		):
			with self.subTest(case):
				frappe.db.set_value("Flow Trigger", self.trigger.name, values, update_modified=False)
				with patch("frappe.enqueue") as enqueue:
					dispatch_scheduled()
				if fires:
					enqueue.assert_called_once_with("frappe.flow.triggers.fire", trigger=self.trigger.name)
					last_fired_at = frappe.db.get_value("Flow Trigger", self.trigger.name, "last_fired_at")
					self.assertGreater(last_fired_at, past)
				else:
					enqueue.assert_not_called()


class TestFire(IntegrationTestCase):
	"""fire() runs the agent on the flow server, here a scripted one."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()
		cls.enterClassContext(patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True))

	def setUp(self):
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}))
		self.daemon = FakeDaemon()
		self.enterContext(patch.object(DaemonClient, "for_site", return_value=self.daemon))
		self.model = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model.name)).insert()
		self.trigger = frappe.get_doc(_trigger(self.agent.name)).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def turns(self):
		return [call for call in self.daemon.calls if call[0] == "run"]

	def test_fire_runs_the_agent_with_the_target_as_its_reference(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "fire test"}).insert()

		run = frappe.get_doc(
			"Flow Run", fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)
		)

		self.assertEqual(
			(run.source, run.trigger, run.status, run.output), ("Trigger", self.trigger.name, "Running", None)
		)
		self.assertEqual((run.reference_doctype, run.reference_name), ("ToDo", todo.name))
		self.assertIn(f"ToDo {todo.name}", run.input)
		session = frappe.get_doc("Flow Session", run.session)
		self.assertEqual((session.agent, session.source), (self.agent.name, "Trigger"))
		# every trigger session runs unattended, so it cannot stop for human approval
		self.assertTrue(session.auto_approve)
		self.assertTrue(self.daemon.configs[run.session]["auto_approve"])
		self.assertEqual(self.turns(), [("run", session.name, run.input)])

		# a scheduled trigger has no target
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

		run = frappe.get_doc("Flow Run", fire(scheduled.name))

		self.assertEqual((run.status, run.trigger), ("Running", scheduled.name))
		self.assertIsNone(run.reference_doctype)
		self.assertIsNone(run.reference_name)

		# a deletion trigger gets the record's last state, since the job runs after it is gone
		deletion = frappe.get_doc(
			_trigger(
				self.agent.name,
				title="Deletion Trigger Test",
				doc_event="on_trash",
				prompt_template="Deleted {{ doc.name }}: {{ doc.description }}",
			)
		).insert()
		gone = frappe.get_doc({"doctype": "ToDo", "description": "delete me"}).insert()
		with patch("frappe.enqueue") as enqueue:
			gone.delete()
		(job,) = [
			call.kwargs for call in enqueue.call_args_list if call.args == ("frappe.flow.triggers.fire",)
		]
		job.pop("enqueue_after_commit")

		run = frappe.get_doc("Flow Run", fire(**job))

		self.assertEqual((run.status, run.trigger), ("Running", deletion.name))
		self.assertIn(f"Deleted {gone.name}: delete me", run.input)
		self.assertIsNone(run.reference_name)

	def test_fire_runs_as_run_as_else_the_owner_not_the_triggering_user(self):
		# Helpdesk scenario: a low-privilege user (no Flow Agent access) fires the trigger by
		# creating a doc; the agent must still run, with the trigger's authority.
		owner = _user("trigger-owner@example.com", "System Manager", FLOW_USER_ROLE)
		service = _user("trigger-service@example.com", "System Manager", FLOW_USER_ROLE)
		customer = _user("trigger-customer@example.com")
		frappe.db.set_value("Flow Trigger", self.trigger.name, "owner", owner)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "help me"}).insert()

		for run_as, account in ((None, owner), (service, service)):
			with self.subTest(run_as=run_as):
				frappe.db.set_value("Flow Trigger", self.trigger.name, "run_as", run_as)
				frappe.set_user(customer)
				run_name = fire(self.trigger.name, target_doctype="ToDo", target_name=todo.name)
				self.assertEqual(frappe.session.user, customer)  # restored afterward
				frappe.set_user("Administrator")

				run = frappe.get_doc("Flow Run", run_name)
				self.assertEqual((run.status, run.owner), ("Running", account))
				self.assertEqual(frappe.get_doc("Flow Session", run.session).owner, account)
				self.assertEqual(self.daemon.configs[run.session]["user_context"]["user"], account)

	def test_fire_skips_without_running_the_agent(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "open", "status": "Open"}).insert()
		for case, values, target in (
			("disabled", {"enabled": 0}, todo.name),
			("target gone", {"enabled": 1}, "does-not-exist"),
			("condition false, rechecked after load", {"condition": "doc.status == 'Closed'"}, todo.name),
		):
			with self.subTest(case):
				frappe.db.set_value("Flow Trigger", self.trigger.name, values)
				self.assertIsNone(fire(self.trigger.name, target_doctype="ToDo", target_name=target))
				self.assertEqual(self.turns(), [])
