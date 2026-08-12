# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation_engine.actions.base import AutomationParamError, get_action, get_action_registry
from frappe.automation_engine.actions.core import (
	AssignToUser,
	CreateDocument,
	IncrementFieldValue,
	SendNotification,
	SetFieldValue,
)
from frappe.tests import IntegrationTestCase


def make_todo(**kwargs):
	return frappe.get_doc({"doctype": "ToDo", "description": "x", **kwargs}).insert()


class TestActions(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.automation_actions = None

	def tearDown(self):
		frappe.db.rollback()
		frappe.local.automation_actions = None

	def test_registry_contains_core_actions(self):
		registry = get_action_registry()
		for action_type in (
			"SetFieldValue",
			"IncrementFieldValue",
			"CreateDocument",
			"SendNotification",
			"AssignToUser",
		):
			self.assertIn(action_type, registry)

	def test_get_action_throws_for_unknown(self):
		self.assertRaises(frappe.ValidationError, get_action, "NopeAction")

	def test_set_field_value_renders_template(self):
		todo = make_todo(priority="Low")
		SetFieldValue().execute(todo, {"field": "priority", "value": "High"}, {})
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")

	def test_set_field_value_validates_field_exists(self):
		self.assertRaises(AutomationParamError, SetFieldValue().validate, {"field": "nope_field"}, "ToDo")

	def test_set_field_value_multiple_fields(self):
		todo = make_todo(priority="Low", color="#000000")
		SetFieldValue().execute(todo, {"values": {"priority": "High", "color": "#ED6396"}}, {})
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "color"), "#ED6396")

	def test_set_field_value_multiple_validates_each_field(self):
		self.assertRaises(
			AutomationParamError,
			SetFieldValue().validate,
			{"values": {"priority": "High", "nope_field": "x"}},
			"ToDo",
		)

	def test_create_document(self):
		src = make_todo()
		detail = CreateDocument().execute(
			src, {"doctype": "ToDo", "values": {"description": "created-by-automation"}}, {}
		)
		self.assertTrue(frappe.db.exists("ToDo", {"description": "created-by-automation"}))
		self.assertIn("Created", detail["detail"])

	def test_increment_field_value(self):
		flow = frappe.new_doc("Automation Flow")
		flow.update({"title": "counter", "trigger_type": "Manual", "date_offset": 2})
		IncrementFieldValue().execute(flow.insert(), {"field": "date_offset", "amount": 3}, {})
		self.assertEqual(frappe.db.get_value("Automation Flow", flow.name, "date_offset"), 5)

	def test_create_document_requires_existing_doctype(self):
		self.assertRaises(
			AutomationParamError, CreateDocument().validate, {"doctype": "No Such DocType"}, "ToDo"
		)

	def test_create_document_renders_template_values(self):
		src = make_todo(priority="High")
		CreateDocument().execute(
			src, {"doctype": "ToDo", "values": {"description": "prio-{{ doc.priority }}"}}, {}
		)
		self.assertTrue(frappe.db.exists("ToDo", {"description": "prio-High"}))

	def test_assign_to_user(self):
		note = frappe.get_doc({"doctype": "Note", "title": "assign-me", "public": 1}).insert()
		AssignToUser().execute(note, {"assign_to": ["Administrator"]}, {})
		assigned = frappe.db.get_value("Note", note.name, "_assign") or ""
		self.assertIn("Administrator", assigned)

	def test_assign_to_user_requires_assignee(self):
		self.assertRaises(AutomationParamError, AssignToUser().validate, {}, "ToDo")

	def test_send_notification_system_creates_log(self):
		todo = make_todo()
		before = frappe.db.count("Notification Log", {"for_user": "Administrator"})
		SendNotification().execute(
			todo,
			{"channel": "System", "recipients": ["Administrator"], "subject": "hi", "message": "there"},
			{},
		)
		after = frappe.db.count("Notification Log", {"for_user": "Administrator"})
		self.assertEqual(after, before + 1)

	def test_send_notification_requires_existing_template(self):
		self.assertRaises(
			AutomationParamError,
			SendNotification().validate,
			{"recipients": ["Administrator"], "email_template": "No Such Template"},
			"ToDo",
		)

	def test_send_notification_renders_email_template(self):
		todo = make_todo(description="templated")
		template = frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": "Automation Test Template",
				"subject": "Subject {{ doc.description }}",
				"response": "Body {{ doc.description }}",
			}
		).insert(ignore_permissions=True)
		subject, message = SendNotification()._content({"email_template": template.name}, todo, {})
		self.assertEqual(subject, "Subject templated")
		self.assertEqual(message, "Body templated")

	def test_send_notification_email_delegates_to_sendmail(self):
		todo = make_todo()
		captured = {}
		original = frappe.sendmail
		frappe.sendmail = lambda **kwargs: captured.update(kwargs)
		try:
			SendNotification().execute(
				todo,
				{"channel": "Email", "recipients": ["a@example.com"], "subject": "s", "message": "m"},
				{},
			)
		finally:
			frappe.sendmail = original
		self.assertEqual(captured["recipients"], ["a@example.com"])
		self.assertEqual(captured["reference_name"], todo.name)
