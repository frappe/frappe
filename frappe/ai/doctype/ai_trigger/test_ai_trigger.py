# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any

import frappe
from frappe.ai.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase


def _model(**overrides: Any) -> dict:
	doc = {
		"doctype": "AI Model",
		"title": "Test Trigger Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "AI Agent",
		"title": "Test Trigger Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _trigger(agent_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "AI Trigger",
		"title": "Test Trigger",
		"agent": agent_name,
		"enabled": 1,
		"event": "DocType Event",
		"target_doctype": "ToDo",
		"doc_event": "after_insert",
		"prompt_template": "A new {{ doc.doctype }} '{{ doc.name }}' was created.",
	}
	doc.update(overrides)
	return doc


class TestAITriggerValidation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_doctype_event_trigger_inserts(self):
		doc = frappe.get_doc(_trigger(self.agent.name)).insert()

		self.assertEqual(doc.event, "DocType Event")
		self.assertEqual(doc.target_doctype, "ToDo")
		self.assertEqual(doc.doc_event, "after_insert")

	def test_doctype_event_requires_target_doctype(self):
		doc = frappe.get_doc(_trigger(self.agent.name, target_doctype=None))
		with self.assertRaisesRegex(frappe.ValidationError, "Target DocType"):
			doc.insert()

	def test_doctype_event_requires_doc_event(self):
		doc = frappe.get_doc(_trigger(self.agent.name, doc_event=None))
		with self.assertRaisesRegex(frappe.ValidationError, "Doc Event"):
			doc.insert()

	def test_scheduled_trigger_inserts_with_cron(self):
		doc = frappe.get_doc(
			_trigger(
				self.agent.name,
				event="Scheduled",
				target_doctype=None,
				doc_event=None,
				cron_expression="0 9 * * 5",
			)
		).insert()

		self.assertEqual(doc.event, "Scheduled")
		self.assertEqual(doc.cron_expression, "0 9 * * 5")

	def test_scheduled_trigger_requires_cron(self):
		doc = frappe.get_doc(
			_trigger(self.agent.name, event="Scheduled", target_doctype=None, doc_event=None)
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Cron"):
			doc.insert()

	def test_scheduled_trigger_rejects_invalid_cron(self):
		doc = frappe.get_doc(
			_trigger(
				self.agent.name,
				event="Scheduled",
				target_doctype=None,
				doc_event=None,
				cron_expression="this is not cron",
			)
		)
		with self.assertRaisesRegex(frappe.ValidationError, "cron"):
			doc.insert()

	def test_invalid_condition_rejected(self):
		doc = frappe.get_doc(_trigger(self.agent.name, condition="doc.status =="))
		with self.assertRaisesRegex(frappe.ValidationError, "condition"):
			doc.insert()

	def test_invalid_prompt_template_rejected(self):
		doc = frappe.get_doc(_trigger(self.agent.name, prompt_template="{{ broken"))
		with self.assertRaisesRegex(frappe.ValidationError, "template"):
			doc.insert()

	def test_unknown_agent_rejected(self):
		doc = frappe.get_doc(_trigger("does-not-exist"))
		with self.assertRaises(frappe.LinkValidationError):
			doc.insert()
