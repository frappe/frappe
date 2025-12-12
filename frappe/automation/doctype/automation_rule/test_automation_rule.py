# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]

emails = ["test_user@example.com", "test_user1@example.com", "test_user2@example.com"]
AUTOMATION_NAME = "Test Automation Rule"
AUTOMATION_RULE = {
	"presets": "doc.status == 'Open'",
	"rule": [
		{
			"type": "if",
			"condition": "doc.priority == 'Medium' ",
			"condition_json": [["priority", "==", "Medium"]],
			"actions": [{"type": "set", "field": "allocated_to", "value": emails[0]}],
		},
		{
			"type": "if",
			"condition": "doc.priority == 'High' ",
			"condition_json": [["priority", "==", "High"]],
			"actions": [{"type": "set", "field": "allocated_to", "value": emails[1]}],
		},
		{
			"type": "else",
			"condition": "True",
			"actions": [{"type": "set", "field": "allocated_to", "value": emails[2]}],
		},
	],
}


class IntegrationTestAutomationRule(IntegrationTestCase):
	"""
	Integration tests for AutomationRule.
	Use this class for testing interactions between multiple components.
	"""

	def setUp(self) -> None:
		for email in emails:
			create_user(email)
		create_base_automation()

	def test_base_automation_rule(self):
		# todo1 with "Medium" priority should be assigned to email[0]
		# todo2 with "High" priority should be assigned to email[1]
		# else todo should be assigned to email[2]
		todo1 = frappe.new_doc("ToDo", priority="Medium", status="Open", description="Test ToDo 1").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(todo1.allocated_to, emails[0])

		todo2 = frappe.new_doc("ToDo", priority="High", status="Open", description="Test ToDo 2").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(todo2.allocated_to, emails[1])

		todo3 = frappe.new_doc("ToDo", priority="Low", status="Open", description="Test ToDo 3").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(todo3.allocated_to, emails[2])

	def tearDown(self) -> None:
		if frappe.db.exists("Automation Rule", AUTOMATION_NAME):
			frappe.delete_doc("Automation Rule", AUTOMATION_NAME)
		for email in emails:
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email)


def create_base_automation():
	if not frappe.db.exists("Automation Rule", AUTOMATION_NAME):
		frappe.new_doc(
			"Automation Rule",
			name=AUTOMATION_NAME,
			dt="ToDo",
			enabled=1,
			doctype_event="On Creation",
			rule=json.dumps(AUTOMATION_RULE),
		).insert(ignore_permissions=True)
