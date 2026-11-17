# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


def _make_agent() -> str:
	model = frappe.get_doc(
		{
			"doctype": "Flow Model",
			"title": "Run Test Model",
			"model_id": "openai/gpt-4o-mini",
			"enabled": 1,
		}
	).insert()
	return (
		frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Run Test Agent",
				"model": model.name,
				"instructions": "x",
				"enabled": 1,
			}
		)
		.insert()
		.name
	)


def _new_session(agent: str) -> str:
	return (
		frappe.get_doc({"doctype": "Flow Session", "agent": agent, "title": "test"})
		.insert(ignore_permissions=True)
		.name
	)


class TestFlowRun(IntegrationTestCase):
	def setUp(self):
		self.agent = _make_agent()

	def tearDown(self):
		frappe.db.rollback()

	def test_a_run_keeps_its_status_and_json_invariants(self):
		session = _new_session(self.agent)
		for fields, error in (
			({"status": "Paused"}, "Paused"),
			({"status": "Failed"}, "Failed"),
			({"status": "Running", "tool_calls": "{not valid json"}, "JSON"),
		):
			doc = frappe.get_doc({"doctype": "Flow Run", "source": "Manual", "session": session, **fields})
			with self.subTest(error), self.assertRaisesRegex(frappe.ValidationError, error):
				doc.insert(ignore_permissions=True)

	def test_a_run_is_not_deleted_on_its_own(self):
		run = frappe.get_doc(
			{
				"doctype": "Flow Run",
				"source": "Manual",
				"session": _new_session(self.agent),
				"status": "Completed",
			}
		).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "belongs to its chat"):
			frappe.delete_doc("Flow Run", run.name)
		self.assertTrue(frappe.db.exists("Flow Run", run.name))
