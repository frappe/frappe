# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.automation_engine.events import emit, registered_events, validate_event
from frappe.automation_engine.registry import clear_automation_cache
from frappe.automation_engine.runner import execute_automation
from frappe.automation_engine.tests.test_runner import make_automation
from frappe.tests import IntegrationTestCase

QUEUE = "Automation Trigger Queue"
SUBSCRIPTION = "Automation Event Subscription"
REPLY_EVENT = "tests.reply"


class TestAutomationEvents(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.hooks = self.patch_hooks({"automation_events": [REPLY_EVENT, "tests.created"]})
		self.hooks.__enter__()
		clear_automation_cache()

	def tearDown(self):
		self.hooks.__exit__(None, None, None)
		frappe.db.rollback()
		clear_automation_cache()

	def test_unregistered_event_is_rejected(self):
		self.assertRaisesRegex(frappe.ValidationError, "Unregistered", emit, "tests.not_registered")

	def test_custom_event_queues_and_executes_docless_flow(self):
		auto = make_automation(
			[
				{
					"action_type": "CreateDocument",
					"params": '{"doctype":"ToDo","values":{"description":"event-created"}}',
				}
			],
			trigger_type="Custom Event",
			document_type=None,
			custom_event="tests.created",
		)
		emit("tests.created", payload={"value": 1})
		execute_automation(frappe.db.get_value(QUEUE, {"automation": auto}, "name"))
		self.assertTrue(frappe.db.exists("ToDo", {"description": "event-created"}))

	def test_event_resumes_waiting_run(self):
		todo, auto = self._wait_flow()
		execute_automation(self._queue(auto, todo.name))
		emit(REPLY_EVENT, correlation_key=todo.name, payload={"reply": True})

		self.assertEqual(self._subscription(auto).status, "Matched")
		execute_automation(self._resume_row(auto))
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")

	def test_wait_times_out_when_no_event_arrives(self):
		todo, auto = self._wait_flow()
		execute_automation(self._queue(auto, todo.name))

		execute_automation(self._resume_row(auto))
		self.assertEqual(self._subscription(auto).status, "Timed Out")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "Low")

	def test_duplicate_emission_resumes_once(self):
		todo, auto = self._wait_flow()
		execute_automation(self._queue(auto, todo.name))

		self.assertEqual(emit(REPLY_EVENT, correlation_key=todo.name)["resumed"], 1)
		self.assertEqual(emit(REPLY_EVENT, correlation_key=todo.name)["resumed"], 0)
		execute_automation(self._resume_row(auto))
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")

	def test_unrelated_correlation_key_does_not_match(self):
		todo, auto = self._wait_flow()
		execute_automation(self._queue(auto, todo.name))

		self.assertEqual(emit(REPLY_EVENT, correlation_key="someone-elses-thread")["resumed"], 0)
		self.assertEqual(self._subscription(auto).status, "Waiting")

	def test_timeout_wins_once_the_deadline_has_passed(self):
		todo, auto = self._wait_flow()
		execute_automation(self._queue(auto, todo.name))
		subscription = self._subscription(auto)
		subscription.db_set("expires_at", frappe.utils.add_days(frappe.utils.now(), -1))

		# An event arriving after the deadline must not steal the timeout branch.
		self.assertEqual(emit(REPLY_EVENT, correlation_key=todo.name)["resumed"], 0)
		execute_automation(self._resume_row(auto))
		self.assertEqual(self._subscription(auto).status, "Timed Out")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "Low")

	def test_flow_deletion_cancels_waiting_subscriptions(self):
		todo, auto = self._wait_flow()
		execute_automation(self._queue(auto, todo.name))
		frappe.delete_doc("Automation Flow", auto, force=True)
		self.assertEqual(frappe.db.count(SUBSCRIPTION, {"event_name": REPLY_EVENT}), 0)

	def _wait_flow(self):
		"""A flow that waits for a reply, then scores the ToDo High (matched) or Low (timeout)."""
		todo = frappe.get_doc({"doctype": "ToDo", "description": "wait-event"}).insert()
		params = {
			"event_name": REPLY_EVENT,
			"correlation_key": "{{ doc.name }}",
			"timeout_value": 2,
			"timeout_unit": "Days",
		}
		auto = make_automation(
			[
				{"step_type": "WaitForEvent", "params": json.dumps(params)},
				{"step_type": "If", "step_condition": "context['event']['outcome'] == 'Matched'"},
				{
					"action_type": "SetFieldValue",
					"parent_step": 2,
					"branch": "If",
					"params": '{"field":"priority","value":"High"}',
				},
				{
					"action_type": "SetFieldValue",
					"parent_step": 2,
					"branch": "Else",
					"params": '{"field":"priority","value":"Low"}',
				},
			]
		)
		return todo, auto

	def _subscription(self, automation):
		"""The single subscription this test's wait flow parked behind."""
		names = frappe.get_all(SUBSCRIPTION, {"event_name": REPLY_EVENT}, pluck="name")
		self.assertEqual(len(names), 1)
		return frappe.get_doc(SUBSCRIPTION, names[0])

	def _resume_row(self, automation):
		return frappe.db.get_value(QUEUE, {"automation": automation, "resume_run": ("is", "set")}, "name")

	def _queue(self, automation, name):
		return (
			frappe.get_doc(
				{
					"doctype": QUEUE,
					"automation": automation,
					"ref_doctype": "ToDo",
					"ref_name": name,
					"status": "Pending",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)


class TestRegisteredEvents(IntegrationTestCase):
	"""Apps may register a bare name or a {name: schema} map; builders read the schema."""

	def setUp(self):
		frappe.set_user("Administrator")
		clear_automation_cache()

	def tearDown(self):
		clear_automation_cache()

	def _events(self, hooks) -> dict:
		with self.patch_hooks({"automation_events": hooks}):
			clear_automation_cache()
			return {item["value"]: item for item in registered_events()}

	def test_bare_name_gets_a_readable_label(self):
		events = self._events(["tests.thing_happened"])

		self.assertEqual(events["tests.thing_happened"]["label"], "Thing happened")
		self.assertEqual(events["tests.thing_happened"]["correlation_options"], [])

	def test_schema_supplies_label_and_correlation_options(self):
		options = [{"label": "This record", "value": "{{ doc.name }}"}]
		events = self._events([{"tests.replied": {"label": "They replied", "correlation_options": options}}])

		self.assertEqual(events["tests.replied"]["label"], "They replied")
		self.assertEqual(events["tests.replied"]["correlation_options"], options)

	def test_a_registered_event_still_validates(self):
		with self.patch_hooks({"automation_events": [{"tests.replied": {}}]}):
			clear_automation_cache()
			validate_event("tests.replied")
			with self.assertRaises(frappe.ValidationError):
				validate_event("tests.unknown")
