# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.user.user import get_system_users
from frappe.desk.doctype.notification_log.notification_log import get_title
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

	def test_get_title_falls_back_to_docname_when_title_is_empty(self):
		note = frappe.get_doc({"doctype": "Note", "title": "Notification title"}).insert()
		frappe.db.set_value("Note", note.name, "title", None, update_modified=False)
		self.assertEqual(get_title("Note", note.name), note.name)


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
