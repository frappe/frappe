# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase


def make_automation(**kwargs):
	doc = frappe.new_doc("Automation Flow")
	doc.title = kwargs.pop("title", "Test Automation")
	doc.trigger_type = kwargs.pop("trigger_type", "Doc Created")
	doc.document_type = kwargs.pop("document_type", "ToDo")
	actions = kwargs.pop("actions", [{"action_type": "SetFieldValue", "params": '{"field": "priority", "value": "Low"}'}])
	for key, value in kwargs.items():
		doc.set(key, value)
	for action in actions:
		doc.append("actions", action)
	return doc


class TestAutomationFlow(IntegrationTestCase):
	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()

	def test_valid_doc_created_automation_saves(self):
		doc = make_automation()
		doc.insert()
		self.assertTrue(doc.name)

	def test_enable_requires_at_least_one_action(self):
		doc = make_automation(enabled=1, actions=[])
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_field_value_changed_requires_trigger_field(self):
		doc = make_automation(trigger_type="Field Value Changed", trigger_field=None)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_scheduled_requires_valid_cron(self):
		doc = make_automation(
			trigger_type="Scheduled", document_type=None, cron_expression="not a cron"
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_scheduled_with_valid_cron_saves(self):
		doc = make_automation(
			trigger_type="Scheduled", document_type=None, cron_expression="0 0 * * *"
		)
		doc.insert()
		self.assertTrue(doc.name)

	def test_child_table_document_type_blocked(self):
		doc = make_automation(document_type="Automation Action")
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_doc_trigger_requires_document_type(self):
		doc = make_automation(document_type=None)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_custom_event_requires_event_name(self):
		doc = make_automation(trigger_type="Custom Event", document_type=None, custom_event=None)
		self.assertRaises(frappe.ValidationError, doc.insert)
