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


def _running_run(session: str):
	return frappe.get_doc(
		{"doctype": "Flow Run", "source": "Manual", "input": "hi", "session": session, "status": "Running"}
	).insert(ignore_permissions=True)


class TestFlowRun(IntegrationTestCase):
	def setUp(self):
		self.agent = _make_agent()

	def tearDown(self):
		frappe.db.rollback()

	def test_mark_failed_sets_status_and_error(self):
		doc = _running_run(_new_session(self.agent))

		doc.mark_failed("something broke")

		self.assertEqual(doc.status, "Failed")
		self.assertEqual(doc.error, "something broke")

	def test_mark_failed_truncates_long_error(self):
		doc = _running_run(_new_session(self.agent))

		doc.mark_failed("x" * 10000)

		self.assertEqual(len(doc.error), 5000)


class TestFlowRunValidation(IntegrationTestCase):
	def setUp(self):
		self.agent = _make_agent()

	def tearDown(self):
		frappe.db.rollback()

	def test_session_is_required(self):
		doc = frappe.get_doc({"doctype": "Flow Run", "source": "Manual", "status": "Running"})
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_paused_without_questions_rejected(self):
		session = _new_session(self.agent)
		doc = frappe.get_doc(
			{"doctype": "Flow Run", "source": "Manual", "status": "Paused", "session": session}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Paused"):
			doc.insert(ignore_permissions=True)

	def test_failed_without_error_rejected(self):
		session = _new_session(self.agent)
		doc = frappe.get_doc(
			{"doctype": "Flow Run", "source": "Manual", "status": "Failed", "session": session}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Failed"):
			doc.insert(ignore_permissions=True)

	def test_invalid_source_rejected(self):
		session = _new_session(self.agent)
		doc = frappe.get_doc(
			{"doctype": "Flow Run", "source": "Bogus", "status": "Running", "session": session}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_invalid_json_field_rejected(self):
		session = _new_session(self.agent)
		doc = frappe.get_doc(
			{
				"doctype": "Flow Run",
				"source": "Manual",
				"status": "Running",
				"session": session,
				"tool_calls": "{not valid json",
			}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "JSON"):
			doc.insert(ignore_permissions=True)
