# -*- coding: utf-8 -*-
# Copyright (c) 2022, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
import unittest

current = frappe.utils.now_datetime()
past = frappe.utils.add_to_date(current, days=-4)
class TestLogSettings(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		fieldnames = ['clear_error_log_after', 'clear_activity_log_after', 'clear_email_queue_after']
		for fieldname in fieldnames:
			frappe.set_value("Log Settings", None, fieldname, 1)

	@classmethod
	def tearDownClass(cls):
		if frappe.db.exists({"doctype": "Activity Log", "subject": "Test subject"}):
			activity_logs = frappe.get_all("Activity Log", filters=dict(subject='Test subject'), pluck='name')
			for log in activity_logs:
				frappe.db.delete("Activity Log", log)

		if frappe.db.exists({"doctype": "Email Queue", "expose_recipients": "test@receiver.com"}):
			email_queues = frappe.get_all("Email Queue", filters=dict(expose_recipients='test@receiver.com'), pluck='name')
			for queue in email_queues:
				frappe.db.delete("Email Queue", queue)

		if frappe.db.exists({"doctype": "Error Log", "method": "test_method"}):
			error_logs = frappe.get_all("Error Log", filters=dict(method='test_method'), pluck='name')
			for log in error_logs:
				frappe.db.delete("Error Log", log)

	def test_create_activity_logs(self):
		doc1 = frappe.get_doc({
					"doctype": "Activity Log",
					"subject": "Test subject",
					"full_name": "test user1",
				})
		doc1.insert(ignore_permissions=True)

		#creation can't be set while inserting new_doc
		frappe.db.set_value("Activity Log", doc1.name, "creation", past)

		doc2 = frappe.get_doc({
					"doctype": "Activity Log",
					"subject": "Test subject",
					"full_name": "test user2",
					"creation": current
				})
		doc2.insert(ignore_permissions=True)

		activity_logs = frappe.get_all("Activity Log", filters=dict(subject='Test subject'), pluck='name')

		self.assertEqual(len(activity_logs), 2)

	def test_create_error_logs(self):
		traceback = """
						Traceback (most recent call last):
							File "apps/frappe/frappe/email/doctype/email_account/email_account.py", line 489, in get_inbound_mails
								messages = email_server.get_messages()
							File "apps/frappe/frappe/email/receive.py", line 166, in get_messages
								if self.has_login_limit_exceeded(e):
							File "apps/frappe/frappe/email/receive.py", line 315, in has_login_limit_exceeded
								return "-ERR Exceeded the login limit" in strip(cstr(e.message))
							AttributeError: 'AttributeError' object has no attribute 'message'
					"""
		doc1 = frappe.get_doc({
					"doctype": "Error Log",
					"method": "test_method",
					"error": traceback,
					"creation": past
				})
		doc1.insert(ignore_permissions=True)

		frappe.db.set_value("Error Log", doc1.name, "creation", past)

		doc2 = frappe.get_doc({
					"doctype": "Error Log",
					"method": "test_method",
					"error": traceback,
					"creation": current
				})
		doc2.insert(ignore_permissions=True)

		error_logs = frappe.get_all("Error Log", filters=dict(method='test_method'), pluck='name')
		self.assertEqual(len(error_logs), 2)

	def test_create_email_queue(self):
		doc1 = frappe.get_doc({
					"doctype": "Email Queue",
					"sender": "test1@example.com",
					"message": "This is a test email1",
					"priority": 1,
					"expose_recipients": "test@receiver.com",
				})
		doc1.insert(ignore_permissions=True)

		frappe.db.set_value("Email Queue", doc1.name, "creation", past)
		frappe.db.set_value("Email Queue", doc1.name, "modified", past, update_modified=False)

		doc2 = frappe.get_doc({
					"doctype": "Email Queue",
					"sender": "test2@example.com",
					"message": "This is a test email2",
					"priority": 1,
					"expose_recipients": "test@receiver.com",
					"creation": current
				})
		doc2.insert(ignore_permissions=True)

		email_queues = frappe.get_all("Email Queue", filters=dict(expose_recipients="test@receiver.com"), pluck='name')

		self.assertEqual(len(email_queues), 2)

	def test_delete_logs(self):
		from frappe.core.doctype.log_settings.log_settings import run_log_clean_up

		run_log_clean_up()

		activity_logs = frappe.get_all("Activity Log", filters=dict(subject='Test subject'), pluck='name')
		self.assertEqual(len(activity_logs), 1)

		error_logs = frappe.get_all("Error Log", filters=dict(method='test_method'), pluck='name')
		self.assertEqual(len(error_logs), 1)

		email_queues = frappe.get_all("Email Queue", filters=dict(expose_recipients='test@receiver.com'), pluck='name')
		self.assertEqual(len(email_queues), 1)

