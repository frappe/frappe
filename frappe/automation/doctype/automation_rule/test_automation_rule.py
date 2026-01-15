# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.core.doctype.communication.test_communication import create_email_account
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.tests import IntegrationTestCase

from .automation_test_rules import *

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]

AUTOMATION_NAME = "Test Automation Rule"


class IntegrationTestAutomationRule(IntegrationTestCase):
	"""
	Integration tests for AutomationRule.
	Use this class for testing interactions between multiple components.
	"""

	def setUp(self) -> None:
		for email in EMAILS:
			create_user(email)

	def test_base_automation_rule(self):
		# todo1 with "Medium" priority should be assigned to email[0]
		# todo2 with "High" priority should be assigned to email[1]
		# else todo should be assigned to email[2]
		create_automation()
		todo1 = frappe.new_doc("ToDo", priority="Medium", status="Open", description="Test ToDo 1").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(todo1.allocated_to, EMAILS[0])

		todo2 = frappe.new_doc("ToDo", priority="High", status="Open", description="Test ToDo 2").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(todo2.allocated_to, EMAILS[1])

		todo3 = frappe.new_doc("ToDo", priority="Low", status="Open", description="Test ToDo 3").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(todo3.allocated_to, EMAILS[2])

	def test_email_send_normal_automation(self):
		# setup email action based automation rule
		create_email_account()
		create_email_template()
		create_automation(name="Test Send Email Automation On Creation", rule=BASE_EMAIL_AUTOMATION_RULE)

		todo1 = frappe.new_doc("ToDo", priority="Medium", status="Open", description="Test ToDo 1").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(todo1.allocated_to, None)
		queue = frappe.get_all("Email Queue")
		self.assertTrue(len(queue), 0)

		todo2 = frappe.new_doc("ToDo", priority="High", status="Open", description="Test ToDo 2").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(todo2.allocated_to, EMAILS[0])

		communications = frappe.get_all(
			"Communication",
			fields=["name", "reference_doctype", "reference_name", "content", "subject"],
			filters={"reference_doctype": "ToDo", "reference_name": todo2.name},
		)
		self.assertTrue(len(communications), 1)
		self.assertIn("Blah Blah Open", communications[0].content)
		self.assertEqual(communications[0].subject, "Blah blah blah")

		queue = frappe.get_all("Email Queue")
		self.assertTrue(len(queue), 2)

	def test_automation_log_creation(self):
		# create 1 day before trigger automation rule
		#
		# date
		time_field = "date"
		create_automation(
			name="Days Offset",
			rule=DAYS_OFFSET_AUTOMATION_RULE,
			doctype_event="Days After",
			time_field=time_field,
			time_offset=1,
		)
		todo1 = frappe.new_doc("ToDo", priority="Medium", status="Open", description="Test ToDo 1").insert(
			ignore_if_duplicate=True
		)
		log_exists = frappe.db.exists(
			"Automation Scheduled Job",
			{
				"reference_doctype": "ToDo",
				"reference_name": todo1.name,
				"automation_rule": "Days Offset",
				"fieldname": time_field,
			},
		)
		# print(frappe.get_all("Automation Scheduled Job", fields=["*"]))

		self.assertTrue(log_exists)

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
		for email in EMAILS:
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email)


def create_automation(name=AUTOMATION_NAME, rule=BASE_AUTOMATION_RULE, **kwargs):
	if not frappe.db.exists("Automation Rule", name):
		doc = frappe.new_doc("Automation Rule")
		doc.update(
			{
				"name": name,
				"dt": "ToDo",
				"enabled": 1,
				"doctype_event": "On Creation",
				"rule": json.dumps(rule),
				**kwargs,
			}
		)
		doc.insert(ignore_permissions=True)


def create_email_template():
	if not frappe.db.exists("Email Template", "Hello"):
		frappe.new_doc(
			"Email Template",
			name="Test Template",
			subject="Hello There",
			template_type="Standard",
			response="The status of your ToDo is: {{status}}",
		).insert(ignore_permissions=True)
