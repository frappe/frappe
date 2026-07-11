# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.automation_engine.actions.base import AutomationAction, get_action_registry
from frappe.automation_engine.registry import clear_automation_cache
from frappe.automation_engine.runner import _failure_key, execute_automation
from frappe.tests import IntegrationTestCase

QUEUE = "Automation Trigger Queue"


def set_field(field, value):
	return {"action_type": "SetFieldValue", "params": json.dumps({"field": field, "value": value})}


def make_todo(**kwargs):
	return frappe.get_doc({"doctype": "ToDo", "description": "x", **kwargs}).insert()


def make_automation(actions, stop_on_error=1):
	doc = frappe.new_doc("Automation")
	doc.title = "Runner Rule"
	doc.trigger_type = "Doc Created"
	doc.document_type = "ToDo"
	doc.stop_on_error = stop_on_error
	for action in actions:
		doc.append("actions", action)
	doc.enabled = 1
	doc.insert()
	return doc.name


class TestRunner(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.automation_actions = None
		clear_automation_cache()

	def tearDown(self):
		frappe.db.rollback()
		frappe.local.automation_actions = None
		clear_automation_cache()

	def queue_row(self, automation, ref_name, depth=1):
		row = frappe.get_doc(
			{
				"doctype": QUEUE,
				"automation": automation,
				"ref_doctype": "ToDo",
				"ref_name": ref_name,
				"status": "Pending",
				"triggered_at": frappe.utils.now(),
				"depth": depth,
			}
		).insert(ignore_permissions=True)
		return row.name

	def run_status(self, automation):
		return frappe.get_all(
			"Automation Run", filters={"automation": automation}, fields=["status"]
		)[0].status

	def test_success_applies_action_and_deletes_queue_row(self):
		todo = make_todo()
		auto = make_automation([set_field("priority", "High")])
		name = self.queue_row(auto, todo.name)
		execute_automation(name)
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")
		self.assertFalse(frappe.db.exists(QUEUE, name))
		self.assertEqual(self.run_status(auto), "Success")

	def test_missing_target_is_skipped(self):
		auto = make_automation([set_field("priority", "High")])
		name = self.queue_row(auto, "NO-SUCH-TODO")
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Skipped")
		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Skipped")

	def test_failed_action_stops_and_marks_failed(self):
		todo = make_todo()
		auto = make_automation([{"action_type": "NopeAction", "params": "{}"}], stop_on_error=1)
		name = self.queue_row(auto, todo.name)
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Failed")
		self.assertEqual(frappe.db.get_value(QUEUE, name, "status"), "Failed")

	def test_partial_failure_continues_when_not_stopping(self):
		todo = make_todo()
		auto = make_automation(
			[{"action_type": "NopeAction", "params": "{}"}, set_field("priority", "High")],
			stop_on_error=0,
		)
		name = self.queue_row(auto, todo.name)
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Partially Failed")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")
		self.assertFalse(frappe.db.exists(QUEUE, name))

	def test_savepoint_rolls_back_failed_action_writes(self):
		class Boom(AutomationAction):
			action_type = "BoomAction"

			def execute(self, doc, params, context):
				frappe.get_doc({"doctype": "ToDo", "description": "ghost-savepoint"}).insert(
					ignore_permissions=True
				)
				raise Exception("boom")

		frappe.local.automation_actions = {**get_action_registry(), "BoomAction": Boom()}
		todo = make_todo()
		auto = make_automation([{"action_type": "BoomAction", "params": "{}"}], stop_on_error=1)
		name = self.queue_row(auto, todo.name)
		execute_automation(name)
		self.assertEqual(self.run_status(auto), "Failed")
		self.assertFalse(frappe.db.exists("ToDo", {"description": "ghost-savepoint"}))

	def test_circuit_breaker_disables_after_threshold(self):
		todo = make_todo()
		auto = make_automation([{"action_type": "NopeAction", "params": "{}"}], stop_on_error=1)
		frappe.cache.delete(_failure_key(auto))
		original = frappe.conf.get("automation_failure_threshold")
		frappe.conf.automation_failure_threshold = 2
		try:
			for _ in range(2):
				execute_automation(self.queue_row(auto, todo.name))
			self.assertEqual(frappe.db.get_value("Automation", auto, "enabled"), 0)
			self.assertTrue(frappe.db.get_value("Automation", auto, "disabled_reason"))
		finally:
			frappe.conf.automation_failure_threshold = original
			frappe.cache.delete(_failure_key(auto))
