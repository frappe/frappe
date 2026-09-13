# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.automation_engine import api
from frappe.automation_engine.registry import clear_automation_cache
from frappe.automation_engine.runner import TASK_METHOD, automation_task_name
from frappe.tests import IntegrationTestCase


def make_automation():
	doc = frappe.new_doc("Automation Flow")
	doc.title = "API Rule"
	doc.trigger_type = "Manual"
	doc.document_type = "ToDo"
	doc.append("actions", {"action_type": "SetFieldValue", "params": '{"field": "priority", "value": "Low"}'})
	doc.enabled = 1
	doc.insert()
	return doc.name


class TestApi(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		clear_automation_cache()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		clear_automation_cache()

	def test_capabilities_lists_triggers_actions_fields(self):
		caps = api.get_automation_capabilities("ToDo")
		self.assertIn("Doc Created", caps["triggers"])
		action_types = [a["action_type"] for a in caps["actions"]]
		self.assertIn("SetFieldValue", action_types)
		self.assertIn("priority", [f["fieldname"] for f in caps["fields"]])

	def test_capabilities_requires_config_permission(self):
		user = frappe.get_doc(
			{"doctype": "User", "email": "auto_noperm@example.com", "first_name": "No Perm"}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		self.assertRaises(frappe.PermissionError, api.get_automation_capabilities, "ToDo")

	def test_validate_action_params_valid(self):
		result = api.validate_action_params("SetFieldValue", "ToDo", json.dumps({"field": "priority"}))
		self.assertTrue(result["valid"])

	def test_validate_action_params_invalid_reports_fieldname(self):
		result = api.validate_action_params("SetFieldValue", "ToDo", json.dumps({}))
		self.assertFalse(result["valid"])
		self.assertEqual(result["errors"][0]["fieldname"], "field")

	def test_validate_action_params_generic_error_has_null_fieldname(self):
		result = api.validate_action_params("SetFieldValue", "No Such DocType", json.dumps({"field": "x"}))
		self.assertFalse(result["valid"])
		self.assertIsNone(result["errors"][0]["fieldname"])

	def test_get_param_options_resolves_doc_fields(self):
		options = api.get_param_options("SetFieldValue", "field", "ToDo")
		self.assertIn("priority", [o["fieldname"] for o in options])

	def test_get_param_options_without_resolver_returns_empty(self):
		# "value" declares no options_source, so no server function is callable for it.
		self.assertEqual(api.get_param_options("SetFieldValue", "value", "ToDo"), [])

	def test_get_param_options_rejects_client_method_paths(self):
		self.assertRaises(
			frappe.ValidationError,
			api.get_param_options,
			"SetFieldValue",
			"field",
			"ToDo",
			json.dumps({"resolver": "frappe.utils.now"}),
		)

	def test_get_param_options_user_search(self):
		options = api.get_param_options("AssignToUser", "assign_to", "ToDo", search_text="Admin")
		self.assertIn("Administrator", [option.name for option in options])

	def test_get_param_options_unknown_field_throws(self):
		self.assertRaises(frappe.ValidationError, api.get_param_options, "SetFieldValue", "bogus", "ToDo")

	def test_run_manually_queues_a_row(self):
		auto = make_automation()
		todo = frappe.get_doc({"doctype": "ToDo", "description": "run-me"}).insert()
		result = api.run_manually(auto, todo.name)
		self.assertTrue(result["queued"])
		self.assertTrue(
			frappe.db.exists(
				"Automation Trigger Queue",
				{"automation": auto, "ref_name": todo.name, "status": "Pending"},
			)
		)
		payload = frappe.db.get_value("Automation Trigger Queue", {"automation": auto}, "event_payload")
		self.assertTrue(json.loads(payload)["manual"])

	def test_get_runs_returns_history(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "history"}).insert()
		frappe.get_doc(
			{
				"doctype": "Background Task",
				"task_id": frappe.generate_hash(length=20),
				"task_name": automation_task_name("AUTO-TEST"),
				"user": frappe.session.user,
				"method": TASK_METHOD,
				"ref_doctype": "ToDo",
				"ref_docname": todo.name,
				"status": "Completed",
				"result": json.dumps({"automation_title": "API Rule", "automation_status": "Success"}),
			}
		).insert(ignore_permissions=True)
		runs = api.get_runs("ToDo", todo.name)
		self.assertEqual(len(runs), 1)
		self.assertEqual(runs[0].status, "Success")
