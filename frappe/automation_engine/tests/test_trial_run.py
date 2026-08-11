# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
from contextlib import contextmanager

import frappe
from frappe.automation_engine.actions.base import get_action_registry
from frappe.automation_engine.api import trial_run
from frappe.automation_engine.runner import automation_task_name
from frappe.automation_engine.tests.test_runner import (
	AutomationRunnerTestCase,
	make_automation,
	make_todo,
	set_field,
)

QUEUE = "Automation Trigger Queue"


@contextmanager
def committing_action():
	"""Make SetFieldValue commit mid-step, the way a third-party action might."""
	handler = get_action_registry()["SetFieldValue"]
	original = handler.execute

	def execute(target, params, context):
		result = original(target, params, context)
		frappe.db.commit()
		return result

	handler.execute = execute
	try:
		yield
	finally:
		handler.execute = original


class TestTrialRun(AutomationRunnerTestCase):
	def test_successful_trial_leaves_nothing_behind(self):
		todo = make_todo(priority="Low")
		auto = make_automation([set_field("priority", "High")])

		result = trial_run(auto, todo.name)

		self.assertEqual(result["status"], "Success")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "Low")
		self.assertFalse(frappe.db.exists(QUEUE, {"automation": auto}))
		self.assertFalse(frappe.db.exists("Background Task", {"task_name": automation_task_name(auto)}))

	def test_failed_step_reports_the_thrown_message_not_a_traceback(self):
		todo = make_todo(priority="Low")
		auto = make_automation([set_field("priority", "Bogus")])

		result = trial_run(auto, todo.name)

		self.assertEqual(result["status"], "Failed")
		step = result["steps"][0]
		self.assertEqual(step["status"], "Failed")
		self.assertIn("Bogus", step["message"])
		self.assertNotIn("Traceback", step["message"])
		self.assertIn("ValidationError", step["exception"])
		self.assertIn("Traceback", step["traceback"])

	def test_skipped_step_reports_the_condition_and_the_values_it_read(self):
		# The real-world bug this exists for: quotes typed into the builder's value box end up
		# inside the needle, so the condition is always false and the step silently never runs.
		todo = make_todo(description="lovelace@gmail.com")
		condition = '"\'@gmail.com\'" in (doc.description or "").lower()'
		auto = make_automation([{**set_field("priority", "High"), "step_condition": condition}])

		result = trial_run(auto, todo.name)

		step = result["steps"][0]
		self.assertEqual(step["status"], "Skipped")
		self.assertEqual(step["condition"], condition)
		self.assertEqual(step["condition_values"], {"doc.description": "lovelace@gmail.com"})

	def test_documents_created_by_the_trial_do_not_survive_it(self):
		todo = make_todo()
		auto = make_automation(
			[
				{
					"action_type": "CreateDocument",
					"params": json.dumps({"doctype": "ToDo", "values": {"description": "trial-artifact"}}),
				}
			]
		)

		result = trial_run(auto, todo.name)

		self.assertEqual(result["status"], "Success")
		self.assertFalse(frappe.db.exists("ToDo", {"description": "trial-artifact"}))

	def test_wait_step_reports_waiting_without_parking_a_resume_row(self):
		todo = make_todo()
		auto = make_automation(
			[
				{"step_type": "Wait", "params": json.dumps({"unit": "Days", "value": 2})},
				set_field("priority", "High"),
			]
		)

		result = trial_run(auto, todo.name)

		self.assertEqual(result["status"], "Waiting")
		self.assertEqual(result["steps"][0]["status"], "Waiting")
		self.assertFalse(frappe.db.exists(QUEUE, {"automation": auto}))

	def test_a_committing_action_still_leaves_nothing_behind(self):
		todo = make_todo(priority="Low")
		auto = make_automation([set_field("priority", "High")])

		with committing_action():
			trial_run(auto, todo.name)

		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "Low")
		self.assertFalse(frappe.db.exists(QUEUE, {"automation": auto}))

	def test_trial_needs_write_on_the_flow(self):
		todo = make_todo()
		auto = make_automation([set_field("priority", "High")])
		user = frappe.get_doc(
			{"doctype": "User", "email": "auto_trial_noperm@example.com", "first_name": "No Perm"}
		).insert(ignore_permissions=True)

		frappe.set_user(user.name)
		self.assertRaises(frappe.PermissionError, trial_run, auto, todo.name)
