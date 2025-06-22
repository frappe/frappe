# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager
from datetime import timedelta

import frappe
import frappe.utils
import frappe.utils.scheduler
from frappe.desk.form import assign_to
from frappe.tests import IntegrationTestCase

from .notification import trigger_notifications

EXTRA_TEST_RECORD_DEPENDENCIES = ["User", "Notification"]


@contextmanager
def get_test_notification(config):
	try:
		notification = frappe.get_doc(doctype="Notification", **config).insert()
		yield notification
	finally:
		notification.delete()
		frappe.db.commit()


class TestNotification(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Email Queue")
		frappe.set_user("test@example.com")

		if not frappe.db.exists("Notification", {"name": "ToDo Status Update"}, "name"):
			notification = frappe.new_doc("Notification")
			notification.name = "ToDo Status Update"
			notification.subject = "ToDo Status Update"
			notification.document_type = "ToDo"
			notification.event = "Value Change"
			notification.value_changed = "status"
			notification.send_to_all_assignees = 1
			notification.set_property_after_alert = "description"
			notification.property_value = "Changed by Notification"
			notification.save()

		if not frappe.db.exists("Notification", {"name": "Contact Status Update"}, "name"):
			notification = frappe.new_doc("Notification")
			notification.name = "Contact Status Update"
			notification.subject = "Contact Status Update"
			notification.document_type = "Contact"
			notification.event = "Value Change"
			notification.value_changed = "status"
			notification.message = "Test Contact Update"
			notification.append("recipients", {"receiver_by_document_field": "email_id,email_ids"})
			notification.save()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_new_and_save(self):
		"""Check creating a new communication triggers a notification."""
		communication = frappe.new_doc("Communication")
		communication.communication_type = "Communication"
		communication.sender_full_name = "__test_notification_sender__"
		communication.subject = "test"
		communication.content = "test"
		communication.insert(ignore_permissions=True)

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{
					"reference_doctype": "Communication",
					"reference_name": communication.name,
					"status": "Not Sent",
				},
			)
		)
		frappe.db.delete("Email Queue")

		communication.reload()
		communication.content = "test 2"
		communication.save()

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{
					"reference_doctype": "Communication",
					"reference_name": communication.name,
					"status": "Not Sent",
				},
			)
		)

		self.assertEqual(frappe.db.get_value("Communication", communication.name, "subject"), "__testing__")

	def test_condition(self):
		"""Check notification is triggered based on a condition."""
		event = frappe.new_doc("Event")
		event.subject = "test"
		event.event_type = "Private"
		event.starts_on = "2014-06-06 12:00:00"
		event.insert()

		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		event.event_type = "Public"
		event.save()

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		# Make sure that we track the triggered notifications in communication doctype.
		self.assertTrue(
			frappe.db.get_value(
				"Communication",
				{
					"reference_doctype": "Event",
					"reference_name": event.name,
					"communication_type": "Automated Message",
				},
			)
		)

	def test_invalid_condition(self):
		frappe.set_user("Administrator")
		notification = frappe.new_doc("Notification")
		notification.subject = "test"
		notification.document_type = "ToDo"
		notification.send_alert_on = "New"
		notification.message = "test"

		recipent = frappe.new_doc("Notification Recipient")
		recipent.receiver_by_document_field = "owner"

		notification.recipents = recipent
		notification.condition = "test"

		self.assertRaises(frappe.ValidationError, notification.save)
		notification.delete()

	def test_value_changed(self):
		event = frappe.new_doc("Event")
		event.subject = "test"
		event.event_type = "Private"
		event.starts_on = "2014-06-06 12:00:00"
		event.insert()

		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		event.subject = "test 1"
		event.save()

		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		event.description = "test"
		event.save()

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

	def test_minutes_positive_offset(self):
		from frappe.utils import add_to_date, now_datetime

		event = frappe.new_doc("Event")
		event.subject = "Test Minutes Positive Offset Event"
		event.event_type = "Private"
		event.starts_on = add_to_date(now_datetime(), minutes=14)
		event.insert()

		# Create a test notification
		notification = {
			"name": "Test Minutes Positive Offset",
			"subject": "Test Minutes Positive Offset",
			"document_type": "Event",
			"event": "Minutes Before",
			"datetime_changed": "starts_on",
			"minutes_offset": 15,
			"message": "Test message",
			"channel": "System Notification",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}

		with get_test_notification(notification) as n:
			frappe.db.delete("Notification Log", {"subject": n.subject})
			# Run the offset alerts
			trigger_notifications(None, "offset")

			# Check if the notification was triggered
			self.assertEqual(1, frappe.db.count("Notification Log", {"subject": n.subject}))

	def test_minutes_negative_offset(self):
		from frappe.utils import add_to_date, now_datetime

		event = frappe.new_doc("Event")
		event.subject = "Test Minutes Negative Offset Event"
		event.event_type = "Private"
		event.starts_on = add_to_date(now_datetime(), minutes=-16)
		event.insert()

		# Create a test notification
		notification = {
			"name": "Test Minutes Negative Offset",
			"subject": "Test Minutes Negative Offset",
			"document_type": "Event",
			"event": "Minutes After",
			"datetime_changed": "starts_on",
			"minutes_offset": 15,
			"message": "Test message",
			"channel": "System Notification",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}

		with get_test_notification(notification) as n:
			frappe.db.delete("Notification Log", {"subject": n.subject})
			# Run the offset alerts
			trigger_notifications(None, "offset")

			# Check if the notification was triggered
			self.assertEqual(1, frappe.db.count("Notification Log", {"subject": n.subject}))

	def test_minutes_offset_validation(self):
		notification = frappe.new_doc("Notification")
		notification.name = "Test Minutes Offset Validation"
		notification.subject = "Test Minutes Offset Validation"
		notification.document_type = "Event"
		notification.event = "Minutes Before"
		notification.datetime_changed = "starts_on"
		notification.message = "Test message"

		# Test negative value
		notification.minutes_offset = -5
		self.assertRaises(frappe.ValidationError, notification.insert)

		# Test zero value
		notification.minutes_offset = 0
		self.assertRaises(frappe.ValidationError, notification.insert)

		# Test value less than 10
		notification.minutes_offset = 5
		self.assertRaises(frappe.ValidationError, notification.insert)

		# Test valid value
		notification.minutes_offset = 15
		notification.insert()
		notification.delete()

	def test_alert_disabled_on_wrong_field(self):
		frappe.set_user("Administrator")
		notification = frappe.get_doc(
			{
				"doctype": "Notification",
				"subject": "_Test Notification for wrong field",
				"document_type": "Event",
				"event": "Value Change",
				"attach_print": 0,
				"value_changed": "description1",
				"message": "Description changed",
				"recipients": [{"receiver_by_document_field": "owner"}],
			}
		).insert()
		frappe.db.commit()  # nosemgrep

		event = frappe.new_doc("Event")
		event.subject = "test-2"
		event.event_type = "Private"
		event.starts_on = "2014-06-06 12:00:00"
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
		event.subject = "test"
		event.event_type = "Private"
		event.starts_on = "2014-01-01 12:00:00"
		event.insert()

		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		frappe.set_user("Administrator")
		frappe.get_doc(
			"Scheduled Job Type",
			dict(method="frappe.email.doctype.notification.notification.trigger_daily_alerts"),
		).execute()

		# not today, so no alert
		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		event.starts_on = frappe.utils.add_days(frappe.utils.nowdate(), 2) + " 12:00:00"
		event.save()

		# Value Change notification alert will be trigger as description is not changed
		# mail will not be sent
		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		frappe.get_doc(
			"Scheduled Job Type",
			dict(method="frappe.email.doctype.notification.notification.trigger_daily_alerts"),
		).execute()

		# today so show alert
		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

	def test_cc_jinja(self):
		frappe.db.delete("User", {"email": "test_jinja@example.com"})
		frappe.db.delete("Email Queue")
		frappe.db.delete("Email Queue Recipient")

		test_user = frappe.new_doc("User")
		test_user.name = "test_jinja"
		test_user.first_name = "test_jinja"
		test_user.email = "test_jinja@example.com"

		test_user.insert(ignore_permissions=True)

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "User", "reference_name": test_user.name, "status": "Not Sent"},
			)
		)

		self.assertTrue(frappe.db.get_value("Email Queue Recipient", {"recipient": "test_jinja@example.com"}))

		frappe.db.delete("User", {"email": "test_jinja@example.com"})
		frappe.db.delete("Email Queue")
		frappe.db.delete("Email Queue Recipient")

	def test_notification_to_assignee(self):
		todo = frappe.new_doc("ToDo")
		todo.description = "Test Notification"
		todo.save()

		assign_to.add(
			{
				"assign_to": ["test2@example.com"],
				"doctype": todo.doctype,
				"name": todo.name,
				"description": "Close this Todo",
			}
		)

		assign_to.add(
			{
				"assign_to": ["test1@example.com"],
				"doctype": todo.doctype,
				"name": todo.name,
				"description": "Close this Todo",
			}
		)

		# change status of todo
		todo.status = "Closed"
		todo.save()

		email_queue = frappe.get_doc(
			"Email Queue", {"reference_doctype": "ToDo", "reference_name": todo.name}
		)

		self.assertTrue(email_queue)

		# check if description is changed after alert since set_property_after_alert is set
		self.assertEqual(todo.description, "Changed by Notification")

		recipients = [d.recipient for d in email_queue.recipients]
		self.assertTrue("test2@example.com" in recipients)
		self.assertTrue("test1@example.com" in recipients)

	def test_notification_by_child_table_field(self):
		contact = frappe.new_doc("Contact")
		contact.first_name = "John Doe"
		contact.status = "Open"
		contact.append("email_ids", {"email_id": "test2@example.com", "is_primary": 1})

		contact.append("email_ids", {"email_id": "test1@example.com"})

		contact.save()

		# change status of contact
		contact.status = "Replied"
		contact.save()

		email_queue = frappe.get_doc(
			"Email Queue", {"reference_doctype": "Contact", "reference_name": contact.name}
		)

		self.assertTrue(email_queue)

		recipients = [d.recipient for d in email_queue.recipients]
		self.assertTrue("test2@example.com" in recipients)
		self.assertTrue("test1@example.com" in recipients)

	def test_notification_value_change_casted_types(self):
		"""Make sure value change event dont fire because of incorrect type comparisons."""
		frappe.set_user("Administrator")

		notification = {
			"document_type": "User",
			"subject": "User changed birthdate",
			"event": "Value Change",
			"channel": "System Notification",
			"value_changed": "birth_date",
			"recipients": [{"receiver_by_document_field": "email"}],
		}

		with get_test_notification(notification) as n:
			frappe.db.delete("Notification Log", {"subject": n.subject})

			user = frappe.get_doc("User", "test@example.com")
			user.birth_date = frappe.utils.add_days(user.birth_date, 1).date()
			user.save()

			user.reload()
			user.birth_date = frappe.utils.getdate(user.birth_date)
			user.save()
			self.assertEqual(1, frappe.db.count("Notification Log", {"subject": n.subject}))

	@classmethod
	def tearDownClass(cls):
		frappe.delete_doc_if_exists("Notification", "ToDo Status Update")
		frappe.delete_doc_if_exists("Notification", "Contact Status Update")

	def test_notification_with_jinja_template(self):
		"""Test Notification with Jinja Template"""
		notification = frappe.get_doc(
			{
				"doctype": "Notification",
				"name": "Notification with Jinja Template",
				"subject": "{{ doc.name }}",
				"document_type": "ToDo",
				"event": "Save",
				"condition": "doc.status == 'Open'",
				"message": "{% set val = frappe.get_doc('ToDo', doc.name) %} ToDo allocated to {{ doc.allocated_to }}",
				"channel": "Email",
				"recipients": [{"receiver_by_document_field": "allocated_to"}],
			}
		).insert()

		todo = frappe.new_doc("ToDo")
		todo.description = "Checking email notification with jinja template"
		todo.allocated_to = "test1@example.com"
		todo.save()

		email_queue = frappe.get_doc(
			"Email Queue", {"reference_doctype": "ToDo", "reference_name": todo.name}
		)
		self.assertTrue(email_queue)

		recipients = [d.recipient for d in email_queue.recipients]
		self.assertTrue("test1@example.com" in recipients)
		self.assertEqual(notification.enabled, 1)


# ruff: noqa: RUF001
"""
PROOF OF TEST for TestNotificationOffsetRange below.

On CI there are uncontrollable side effects which force the commenting out of this test.

❯ bench run-tests --module frappe.email.doctype.notification.test_notification --case TestNotificationOffsetRange
/nix/store/la0hqc6s2n2rd50b5sn13m33av6jx9zl-python3-3.11.9-env/lib/python3.11/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
  from crypt import crypt as _crypt
Updating Dashboard for frappe
/nix/store/la0hqc6s2n2rd50b5sn13m33av6jx9zl-python3-3.11.9-env/lib/python3.11/site-packages/cssutils/_fetchgae.py:6: DeprecationWarning: 'cgi' is deprecated and slated for removal in Python 3.13
  import cgi
...
----------------------------------------------------------------------
Ran 3 tests in 2.677s

OK
"""


# from frappe.utils import add_to_date, now_datetime
# class TestNotificationOffsetRange(IntegrationTestCase):
# 	def setUp(self):
# 		frappe.set_user("test@example.com")
# 		# Create an event and notification before each test
# 		self.event = frappe.new_doc("Event")
# 		self.event.subject = "Test Event for Offset Range"
# 		self.event.event_type = "Private"
# 		self.event.starts_on = now_datetime()
# 		self.event.insert()

# 		self.notification = {
# 			"name": "Test Offset Range",
# 			"subject": "Test Offset Range",
# 			"document_type": "Event",
# 			"event": "Minutes Before",
# 			"datetime_changed": "starts_on",
# 			"minutes_offset": 15,
# 			"message": "Test message",
# 			"channel": "System Notification",
# 			"recipients": [{"receiver_by_document_field": "owner"}],
# 		}

# 	def tearDown(self):
# 		frappe.set_user("Administrator")
# 		# Clean up after each test
# 		frappe.db.delete("Event", {"name": self.event.name})
# 		frappe.db.delete("Notification", {"name": self.notification["name"]})
# 		frappe.db.delete("Notification Log", {"subject": self.notification["subject"]})

# 	def test_notification_offset_range(self):
# 		with get_test_notification(self.notification) as n:
# 			# Test for 25 minutes before and after the event start time
# 			start_time = add_to_date(self.event.starts_on, minutes=-25)
# 			end_time = add_to_date(self.event.starts_on, minutes=25)
# 			current_time = start_time

# 			while current_time <= end_time:
# 				with self.freeze_time(current_time):
# 					frappe.db.delete("Notification Log", {"subject": n.subject})
# 					trigger_notifications(None, "offset")

# 					time_diff = (self.event.starts_on - current_time).total_seconds() / 60

# 					if 15 >= time_diff > 10:  # 15 to 11 minutes before (5-minute window)
# 						# The notification should be triggered within this 5-minute window
# 						self.assertEqual(
# 							1,
# 							frappe.db.count("Notification Log", {"subject": n.subject}),
# 							f"Notification not triggered at {current_time:%H:%M} (offset -{time_diff:.0f}) and between ]15,10] min prior to {self.event.starts_on:%H:%M}",
# 						)
# 					else:
# 						# The notification should not be triggered at any other time
# 						self.assertEqual(
# 							0,
# 							frappe.db.count("Notification Log", {"subject": n.subject}),
# 							f"Notification incorrectly triggered at {current_time:%H:%M}",
# 						)

# 				current_time += timedelta(minutes=3)  # Move in 3-minute increments

# 	def test_notification_offset_range_after(self):
# 		# Modify the notification to test "Minutes After"
# 		self.notification["event"] = "Minutes After"

# 		with get_test_notification(self.notification) as n:
# 			# Test for 25 minutes before and after the event start time
# 			start_time = add_to_date(self.event.starts_on, minutes=-25)
# 			end_time = add_to_date(self.event.starts_on, minutes=25)
# 			current_time = start_time

# 			while current_time <= end_time:
# 				with self.freeze_time(current_time):
# 					frappe.db.delete("Notification Log", {"subject": n.subject})
# 					trigger_notifications(None, "offset")

# 					time_diff = (current_time - self.event.starts_on).total_seconds() / 60

# 					if 15 <= time_diff < 20:  # 15 to 19 minutes after (5-minute window)
# 						# The notification should be triggered within this 5-minute window
# 						self.assertEqual(
# 							1,
# 							frappe.db.count("Notification Log", {"subject": n.subject}),
# 							f"Notification not triggered at {current_time:%H:%M} (offset +{time_diff:.0f}) and between [15,20[ min after {self.event.starts_on:%H:%M}",
# 						)
# 					else:
# 						# The notification should not be triggered at any other time
# 						self.assertEqual(
# 							0,
# 							frappe.db.count("Notification Log", {"subject": n.subject}),
# 							f"Notification incorrectly triggered at {current_time:%H:%M}",
# 						)

# 				current_time += timedelta(minutes=3)  # Move in 3-minute increments

# 	def test_notification_offset_edge_cases(self):
# 		# Test edge cases of the 5-minute window
# 		edge_cases = {
# 			"Minutes Before": [15, 11, 10],  # last should not trigger
# 			"Minutes After": [15, 19, 20],  # last should not trigger
# 		}  # minutes before/after event
# 		for event_type in ["Minutes Before", "Minutes After"]:
# 			self.notification["event"] = event_type
# 			for minutes in edge_cases[event_type]:
# 				with get_test_notification(self.notification) as n:
# 					if event_type == "Minutes Before":
# 						test_time = add_to_date(self.event.starts_on, minutes=-minutes)
# 					else:
# 						test_time = add_to_date(self.event.starts_on, minutes=minutes)

# 					with self.freeze_time(test_time):
# 						frappe.db.delete("Notification Log", {"subject": n.subject})
# 						trigger_notifications(None, "offset")

# 						if minutes != edge_cases[event_type][-1]:
# 							self.assertEqual(
# 								1,
# 								frappe.db.count("Notification Log", {"subject": n.subject}),
# 								f"Notification not triggered at edge case: {minutes} {event_type}",
# 							)
# 						else:
# 							self.assertEqual(
# 								0,
# 								frappe.db.count("Notification Log", {"subject": n.subject}),
# 								f"Notification incorrectly triggered at edge case: {minutes} {event_type}",
# 							)
