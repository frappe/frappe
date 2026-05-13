# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.user.user import get_system_users
from frappe.desk.doctype.notification_log.notification_log import mark_all_as_read, mark_as_read
from frappe.desk.doctype.notification_settings.notification_settings import create_notification_settings
from frappe.desk.form.assign_to import add as assign_task
from frappe.tests import IntegrationTestCase


class TestNotificationLog(IntegrationTestCase):
	def test_assignment(self):
		todo = get_todo()
		user = get_user()

		assign_task(
			{"assign_to": [user], "doctype": "ToDo", "name": todo.name, "description": todo.description}
		)
		log_type = frappe.db.get_value(
			"Notification Log", {"document_type": "ToDo", "document_name": todo.name}, "type"
		)
		self.assertEqual(log_type, "Assignment")

	def test_share(self):
		todo = get_todo()
		user = get_user()

		frappe.share.add("ToDo", todo.name, user, notify=1)
		log_type = frappe.db.get_value(
			"Notification Log", {"document_type": "ToDo", "document_name": todo.name}, "type"
		)
		self.assertEqual(log_type, "Share")

		email = get_last_email_queue()
		content = f"Subject: {frappe.utils.get_fullname(frappe.session.user)} shared a document ToDo"
		self.assertTrue(content in email.message)


class TestNotificationUnreadCount(IntegrationTestCase):
	def setUp(self):
		self.user = "test@example.com"
		create_notification_settings(self.user)
		frappe.db.delete("Notification Log", {"for_user": self.user})
		frappe.db.set_value("Notification Settings", self.user, "unread_count", 0, update_modified=False)
		frappe.clear_document_cache("Notification Settings", self.user)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Notification Log", {"for_user": self.user})

	def _insert_log(self, for_user=None):
		return frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": "test",
				"for_user": for_user or self.user,
				"from_user": "Administrator",
				"type": "Alert",
			}
		).insert(ignore_permissions=True)

	def _count(self, user=None):
		return frappe.db.get_value("Notification Settings", user or self.user, "unread_count")

	def test_insert_and_mark_as_read(self):
		log = self._insert_log()
		self._insert_log()
		self.assertEqual(self._count(), 2)

		frappe.set_user(self.user)
		mark_as_read(log.name)
		self.assertEqual(self._count(), 1)
		self.assertEqual(frappe.db.get_value("Notification Log", log.name, "read"), 1)

		mark_as_read(log.name)
		self.assertEqual(self._count(), 1)

	def test_mark_as_read_ignores_other_user(self):
		other_user = "test1@example.com"
		create_notification_settings(other_user)
		frappe.db.set_value("Notification Settings", other_user, "unread_count", 0, update_modified=False)
		frappe.db.delete("Notification Log", {"for_user": other_user})
		log = self._insert_log(for_user=other_user)

		frappe.set_user(self.user)
		mark_as_read(log.name)

		self.assertEqual(self._count(other_user), 1)
		self.assertEqual(frappe.db.get_value("Notification Log", log.name, "read"), 0)

		frappe.set_user("Administrator")
		frappe.db.delete("Notification Log", {"for_user": other_user})

	def test_mark_all_as_read(self):
		for _ in range(3):
			self._insert_log()
		frappe.set_user(self.user)
		mark_all_as_read()
		self.assertEqual(self._count(), 0)

		self._insert_log()
		self._insert_log()
		frappe.db.set_value("Notification Settings", self.user, "unread_count", 1, update_modified=False)
		frappe.clear_document_cache("Notification Settings", self.user)
		mark_all_as_read()
		self.assertEqual(self._count(), 0)


def get_last_email_queue():
	res = frappe.get_all("Email Queue", fields=["message"], order_by="creation desc", limit=1)
	return res[0]


def get_todo():
	if not frappe.get_all("ToDo"):
		return frappe.get_doc({"doctype": "ToDo", "description": "Test for Notification"}).insert()

	res = frappe.get_all("ToDo", limit=1)
	return frappe.get_cached_doc("ToDo", res[0].name)


def get_user():
	return get_system_users(limit=1)[0]
