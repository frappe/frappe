# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe, frappe.utils, frappe.utils.scheduler
import unittest

test_records = frappe.get_test_records('Notification')

test_dependencies = ["User"]

class TestNotification(unittest.TestCase):
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

		self.assertEqual(frappe.db.get_value('Communication',
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
		notification = frappe.new_doc("Notification")
		notification.subject = "test"
		notification.document_type = "ToDo"
		notification.send_alert_on = "New"
		notification.message = "test"

		recipent = frappe.new_doc("Notification Recipient")
		recipent.email_by_document_field = "owner"

		notification.recipents = recipent
		notification.condition = "test"

		self.assertRaises(frappe.ValidationError, notification.save)
		notification.delete()


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
		notification = frappe.get_doc({
			"doctype": "Notification",
			"subject":"_Test Notification for wrong field",
			"document_type": "Event",
			"event": "Value Change",
			"attach_print": 0,
			"value_changed": "description1",
			"message": "Description changed",
			"recipients": [
				{ "email_by_document_field": "owner" }
			]
		}).insert()
		frappe.db.commit()

		event = frappe.new_doc("Event")
		event.subject = "test-2",
		event.event_type = "Private"
		event.starts_on  = "2014-06-06 12:00:00"
		event.insert()
		event.subject = "test 1"
		event.save()

		# verify that notification is disabled
		notification.reload()
		self.assertEqual(notification.enabled, 0)
		notification.delete()
		event.delete()

	def test_date_changed(self):

		event = frappe.new_doc("Event")
		event.subject = "test",
		event.event_type = "Private"
		event.starts_on = "2014-01-01 12:00:00"
		event.insert()

		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status": "Not Sent"}))

		frappe.set_user('Administrator')
		frappe.utils.scheduler.trigger(frappe.local.site, "daily", now=True)

		# not today, so no alert
		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status": "Not Sent"}))

		event.starts_on  = frappe.utils.add_days(frappe.utils.nowdate(), 2) + " 12:00:00"
		event.save()

		# Value Change notification alert will be trigger as description is not changed
		# mail will not be sent
		self.assertFalse(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status": "Not Sent"}))

		frappe.utils.scheduler.trigger(frappe.local.site, "daily", now=True)

		# today so show alert
		self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": "Event",
			"reference_name": event.name, "status":"Not Sent"}))

	def test_cc_jinja(self):

		frappe.db.sql("""delete from `tabUser` where email='test_jinja@example.com'""")
		frappe.db.sql("""delete from `tabEmail Queue`""")
		frappe.db.sql("""delete from `tabEmail Queue Recipient`""")

		test_user = frappe.new_doc("User")
		test_user.name = 'test_jinja'
		test_user.first_name = 'test_jinja'
		test_user.email = 'test_jinja@example.com'

		test_user.insert(ignore_permissions=True)

		self.assertTrue(frappe.db.get_value("Email Queue", {"reference_doctype": "User",
			"reference_name": test_user.name, "status":"Not Sent"}))

		self.assertTrue(frappe.db.get_value("Email Queue Recipient", {"recipient": "test_jinja@example.com"}))

		frappe.db.sql("""delete from `tabUser` where email='test_jinja@example.com'""")
		frappe.db.sql("""delete from `tabEmail Queue`""")
		frappe.db.sql("""delete from `tabEmail Queue Recipient`""")
