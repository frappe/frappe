# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.core.doctype.communication.test_communication import create_email_account
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
	"presets": [["status", "equals", "Open"]],
	"rule": [
		{
			"type": "if",
			"conditions": [["priority", "equals", "Medium"]],
			"actions": [{"type": "set", "field": "allocated_to", "value": emails[0]}],
		},
		{
			"type": "if",
			"conditions": [["priority", "equals", "High"]],
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

	def test_base_automation_rule(self):
		# todo1 with "Medium" priority should be assigned to email[0]
		# todo2 with "High" priority should be assigned to email[1]
		# else todo should be assigned to email[2]
		create_base_automation()
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

	def test_email_send_normal_automation(self):
		# setup email action based automation rule
		create_email_account()
		frappe.sendmail(
			recipients=["test_recipient@example.com"],
			subject="Test Subject",
			message="Test message",
		)
		queue = frappe.get_all("Email Queue")
		self.assertTrue(len(queue), 1)
		# email account setup needed
		# create todo to trigger automation rule
		# email queue entry should be present
		pass

	def test_automation_log_creation(self):
		# create 1 day before trigger automation rule
		#
		pass
		# todo1 = frappe.new_doc("ToDo", priority="Medium", status="Open", description="Test ToDo 1").insert(
		# 	ignore_if_duplicate=True
		# )
		# log should be created in Automation Scheduled Job Log
		# self.assertTrue(
		# 	frappe.db.exists(
		# 		"Automation Scheduled Job Log",
		# 		{"reference_doctype": "ToDo", "reference_name": todo1.name, "automation_rule": AUTOMATION_NAME},
		# 	)
		# )

	def test_time_based_automation(self):
		# time based automation rule create
		# todo create
		# job schculed in log
		# increase time by 5 minutes
		# communication created?  + email queue is present or not + value set or not
		pass

	def test_automation_rule_update(self):
		pass

	def test_automation_rule_deletion(self):
		pass

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
