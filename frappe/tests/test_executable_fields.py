# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import json
from unittest.mock import patch

import frappe
from frappe.api import v2
from frappe.core.doctype.deleted_document.deleted_document import restore
from frappe.core.doctype.user.test_user import test_user
from frappe.email.doctype.notification.notification import Notification
from frappe.handler import run_doc_method
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request


def make_notification(**values):
	return frappe.get_doc(
		{
			"doctype": "Notification",
			"name": frappe.generate_hash(length=10),
			"channel": "Email",
			"document_type": "ToDo",
			"event": "New",
			"enabled": 0,
			"subject": "Hi {{ doc.name }}",
			"message": "{{ doc.description }}",
			"condition": "doc.status == 'Open'",
			"recipients": [{"receiver_by_document_field": "owner", "cc": "{{ doc.owner }}"}],
			**values,
		}
	).insert()


class TestExecutableFields(IntegrationTestCase):
	def setUp(self):
		self.notification = make_notification()

	def test_non_author_cannot_change_code(self):
		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			doc = frappe.get_doc("Notification", self.notification.name)
			doc.enabled = 1
			doc.save()

			doc.condition = "doc.status == 'Closed'"
			self.assertRaises(frappe.PermissionError, doc.save)

			doc.reload()
			doc.condition = None
			doc.save()

	def test_author_can_change_code(self):
		for role in ("Code Author", "Script Manager"):
			with self.subTest(role=role), test_user(roles=["System Manager", role]) as user:
				with self.set_user(user.name):
					doc = frappe.get_doc("Notification", self.notification.name)
					doc.condition = f"doc.status == '{role}'"
					doc.save()

	def test_copy_allowance(self):
		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			make_notification()
			for condition in ("doc.status == 'Closed'", "doc.status == 'OPEN'"):
				with self.subTest(condition=condition):
					self.assertRaises(frappe.PermissionError, make_notification, condition=condition)

	def test_child_rows(self):
		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			doc = frappe.get_doc("Notification", self.notification.name)
			doc.append("recipients", {"receiver_by_role": "System Manager"})
			doc.save()

			doc.append("recipients", {"receiver_by_role": "System Manager", "condition": "doc.status"})
			self.assertRaises(frappe.PermissionError, doc.save)

			doc.reload()
			doc.recipients = [row for row in doc.recipients if not row.cc]
			doc.save()

	def test_unsaved_doc_methods(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "preview"}).insert()
		saved = self.notification.as_dict(convert_dates_to_str=True)
		edited = {**saved, "message": "{{ frappe.session.user }}"}
		set_request(method="POST", path="/")

		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			run_doc_method("preview_message", docs=json.dumps(saved), args={"preview_document": todo.name})
			for call in (
				lambda: run_doc_method(
					"preview_message", docs=json.dumps(edited), args={"preview_document": todo.name}
				),
				lambda: v2.run_doc_method("preview_message", edited, {"preview_document": todo.name}),
			):
				self.assertRaises(frappe.PermissionError, call)

	def test_restore_deleted_document(self):
		# code no other document holds, so the restore can't pass as a copy
		tag = frappe.generate_hash(length=10)
		notification = make_notification(
			subject=f"{tag} {{{{ doc.name }}}}",
			message=f"{tag} {{{{ doc.description }}}}",
			condition=f"doc.description == '{tag}'",
			recipients=[{"receiver_by_document_field": "owner", "cc": f"{{{{ doc.owner }}}} {tag}"}],
		)
		notification.delete()
		deleted = frappe.db.get_value(
			"Deleted Document", {"deleted_doctype": "Notification", "deleted_name": notification.name}
		)
		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			restore(deleted, alert=False)
		self.assertTrue(frappe.db.exists("Notification", notification.name))

	def test_standard_notification_message_from_app_file(self):
		frappe.db.set_value("Notification", self.notification.name, {"is_standard": 1, "module": "Email"})
		app_file = "From the app {{ doc.name }}"

		with (
			patch.object(Notification, "get_template", return_value=app_file),
			# saving a standard notification exports it to files in developer mode
			patch("frappe.email.doctype.notification.notification.export_module_json", return_value=None),
			test_user(roles=["System Manager"]) as user,
			self.set_user(user.name),
		):
			doc = frappe.get_doc("Notification", self.notification.name)
			doc.run_method("onload")
			doc.enabled = 0
			doc.save()

			doc.message = "{{ frappe.session.user }}"
			self.assertRaises(frappe.PermissionError, doc.save)
