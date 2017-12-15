# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe, frappe.utils, frappe.utils.scheduler
import unittest

test_records = frappe.get_test_records('Email Alert')

test_dependencies = ["User"]

class TestEmailAlert(unittest.TestCase):
	def setUp(self):
		frappe.db.sql("""delete from `tabEmail Queue`""")
		frappe.set_user("test1@example.com")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_new_and_save(self):
		communication = frappe.new_doc("Communication")
		communication.communication_type = 'Comment'
		communication.subject = "test"
		communication.content = "test"
		communication.insert(ignore_permissions=True)

		self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": "Communication",
			"reference_name": communication.name, "status":"Not Sent"}))
		frappe.db.sql("""delete from `tabEmail Queue`""")

		communication.content = "test 2"
		communication.save()

		self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": "Communication",
			"reference_name": communication.name, "status":"Not Sent"}))

		self.assertEquals(frappe.db.get_value('Communication',
			communication.name, 'subject'), '__testing__')

	def test_condition(self):
		event = frappe.new_doc("Event")
		event.subject = "test",
		event.event_type = "Private"
		event.starts_on  = "2014-06-06 12:00:00"
		event.insert()

		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

		event.event_type = "Public"
		event.save()

		self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

	def test_invalid_condition(self):
		frappe.set_user("Administrator")
		email_alert = frappe.new_doc("Email Alert")
		email_alert.subject = "test"
		email_alert.document_type = "ToDo"
		email_alert.send_alert_on = "New"
		email_alert.message = "test"

		recipent = frappe.new_doc("Email Alert Recipient")
		recipent.email_by_document_field = "owner"

		email_alert.recipents = recipent
		email_alert.condition = "test"

		self.assertRaises(frappe.ValidationError, email_alert.save)


	def test_value_changed(self):
		event = frappe.new_doc("Event")
		event.subject = "test",
		event.event_type = "Private"
		event.starts_on  = "2014-06-06 12:00:00"
		event.insert()

		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

		event.subject = "test 1"
		event.save()

		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

		event.description = "test"
		event.save()

		self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

	def test_alert_disabled_on_wrong_field(self):
		frappe.set_user('Administrator')
		email_alert = frappe.get_doc({
			"doctype": "Email Alert",
			"subject":"_Test Email Alert for wrong field",
			"document_type": "Event",
			"event": "Value Change",
			"attach_print": 0,
			"value_changed": "description1",
			"message": "Description changed",
			"recipients": [
				{ "email_by_document_field": "owner" }
			]
		}).insert()

		event = frappe.new_doc("Event")
		event.subject = "test-2",
		event.event_type = "Private"
		event.starts_on  = "2014-06-06 12:00:00"
		event.insert()
		event.subject = "test 1"
		event.save()

		# verify that email_alert is disabled
		email_alert.reload()
		self.assertEqual(email_alert.enabled, 0)
		email_alert.delete()
		event.delete()


	def test_date_changed(self):
		event = frappe.new_doc("Event")
		event.subject = "test",
		event.event_type = "Private"
		event.starts_on = "2014-01-01 12:00:00"
		event.insert()

		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

		frappe.utils.scheduler.trigger(frappe.local.site, "daily", now=True)

		# not today, so no alert
		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

		event.starts_on  = frappe.utils.add_days(frappe.utils.nowdate(), 2) + " 12:00:00"
		event.save()

		# Value Change email alert alert will be trigger as description is not changed
		# mail will not be sent
		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

		frappe.utils.scheduler.trigger(frappe.local.site, "daily", now=True)

		# today so show alert
		self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))
