# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.tests import IntegrationTestCase


def set_field(field, value):
	return {"action_type": "SetFieldValue", "params": json.dumps({"field": field, "value": value})}


def make_automation(**kwargs):
	doc = frappe.new_doc("Automation Flow")
	doc.title = kwargs.pop("title", "Test Automation")
	doc.trigger_type = kwargs.pop("trigger_type", "Doc Created")
	doc.document_type = kwargs.pop("document_type", "ToDo")
	actions = kwargs.pop("actions", [_default_action(doc.document_type)])
	for key, value in kwargs.items():
		doc.set(key, value)
	for action in actions:
		doc.append("actions", action)
	return doc


def _default_action(document_type):
	if document_type:
		return {"action_type": "SetFieldValue", "params": '{"field": "priority", "value": "Low"}'}
	return {"action_type": "CreateDocument", "params": '{"doctype": "ToDo"}'}


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
		doc = make_automation(trigger_type="Scheduled", document_type=None, cron_expression="not a cron")
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_scheduled_with_valid_cron_saves(self):
		doc = make_automation(trigger_type="Scheduled", document_type=None, cron_expression="0 0 * * *")
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

	def test_else_step_type_rejected(self):
		"""Else is not a step — the two arms are the children's `branch` values."""
		doc = make_automation(actions=[{"step_type": "Else", "params": "{}"}])
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_if_step_requires_condition(self):
		doc = make_automation(actions=[{"step_type": "If", "params": "{}"}])
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_branch_requires_an_if_parent(self):
		doc = make_automation(
			actions=[
				set_field("priority", "Low"),
				{**set_field("priority", "High"), "parent_step": 1, "branch": "If"},
			]
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_branch_parent_must_be_earlier(self):
		doc = make_automation(
			actions=[
				{**set_field("priority", "High"), "parent_step": 2, "branch": "If"},
				{"step_type": "If", "step_condition": "True"},
			]
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_branch_without_parent_step_rejected(self):
		doc = make_automation(actions=[{**set_field("priority", "Low"), "branch": "If"}])
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_branching_flow_saves_and_enables(self):
		doc = make_automation(
			enabled=1,
			actions=[
				{"step_type": "If", "step_condition": "doc.priority == 'High'"},
				{**set_field("status", "Open"), "parent_step": 1, "branch": "If"},
				{**set_field("status", "Closed"), "parent_step": 1, "branch": "Else"},
			],
		)
		doc.insert()
		self.assertTrue(doc.name)

	def test_wait_step_requires_duration(self):
		doc = make_automation(actions=[{"step_type": "Wait", "params": "{}"}])
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_wait_step_rejects_unknown_unit(self):
		doc = make_automation(actions=[{"step_type": "Wait", "params": '{"value": 5, "unit": "weeks"}'}])
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_wait_step_with_duration_saves(self):
		doc = make_automation(actions=[{"step_type": "Wait", "params": '{"value": 5, "unit": "Seconds"}'}])
		doc.insert()
		self.assertTrue(doc.name)

	def test_enabling_wait_containing_flow_allowed(self):
		doc = make_automation(
			enabled=1,
			actions=[
				set_field("priority", "Low"),
				{"step_type": "Wait", "params": '{"value": 5, "unit": "Seconds"}'},
			],
		)
		doc.insert()
		self.assertTrue(doc.name)

	def test_enabling_custom_event_flow_blocked(self):
		doc = make_automation(
			trigger_type="Custom Event", document_type=None, custom_event="deal_won", enabled=1
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_custom_event_flow_saves_as_draft(self):
		doc = make_automation(trigger_type="Custom Event", document_type=None, custom_event="deal_won")
		doc.insert()
		self.assertTrue(doc.name)

	def test_date_based_flow_enables(self):
		doc = make_automation(
			trigger_type="Date Based", date_field="date", date_direction="Before", date_offset=3, enabled=1
		)
		doc.insert()
		self.assertTrue(doc.name)

	def test_date_based_requires_field_and_direction(self):
		doc = make_automation(trigger_type="Date Based", date_field=None, date_direction=None)
		self.assertRaises(frappe.ValidationError, doc.insert)
