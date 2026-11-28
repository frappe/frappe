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

	def test_unticking_a_check_is_not_authoring(self):
		page = frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": frappe.generate_hash(length=10),
				"route": frappe.generate_hash(length=10),
				"published": 1,
				"dynamic_template": 1,
				"main_section": "<p>Static</p>",
			}
		).insert()

		with test_user(roles=["System Manager", "Website Manager"]) as user, self.set_user(user.name):
			page.reload()
			page.dynamic_template = 0
			page.save()

			page.dynamic_template = 1
			self.assertRaises(frappe.PermissionError, page.save)

	def test_notification_cannot_set_code_field_after_alert(self):
		template = frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": frappe.generate_hash(length=10),
				"subject": "Hi",
				"response": "Hello",
			}
		).insert()
		values = {
			"document_type": "Email Template",
			"email_template": template.name,
			"subject": None,
			"message": None,
			"condition": None,
			"recipients": [{"receiver_by_document_field": "owner"}],
			"set_property_after_alert": "subject",
			"property_value": "{{ frappe.session.user }}",
		}

		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			self.assertRaises(frappe.PermissionError, make_notification, **values)

			# a field that runs nothing stays available
			notification = make_notification(
				**{**values, "set_property_after_alert": "use_html", "property_value": "0"}
			)
			notification.property_value = "1"
			notification.save()

			# retargeting counts, and so does template syntax in a field that is code only with Jinja
			notification = make_notification(
				**{
					**values,
					"document_type": "Communication",
					"set_property_after_alert": "subject",
					"property_value": "Hi",
				}
			)
			notification.document_type = "Email Template"
			self.assertRaises(frappe.PermissionError, notification.save)

			page = {**values, "document_type": "Web Page", "set_property_after_alert": "main_section_html"}
			self.assertRaises(frappe.PermissionError, make_notification, **page)
			make_notification(**{**page, "property_value": "<p>Plain</p>"})

		with test_user(roles=["System Manager", "Code Author"]) as user, self.set_user(user.name):
			make_notification(**values)

	def test_webhook_url_is_code_only_when_dynamic(self):
		values = {
			"doctype": "Webhook",
			"webhook_doctype": "ToDo",
			"webhook_docevent": "after_insert",
			"request_url": "https://example.com/hook",
		}

		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			webhook = frappe.get_doc({**values, "name": frappe.generate_hash(length=10)}).insert()

			webhook.request_url = "https://example.com/{{ frappe.session.user }}"
			webhook.save()

			webhook.is_dynamic_url = 1
			self.assertRaises(frappe.PermissionError, webhook.save)

			# a static URL is no source for a dynamic copy, even next to another dynamic webhook
			webhook.reload()
			dynamic = {
				**values,
				"name": frappe.generate_hash(length=10),
				"request_url": "https://example.com/{{ doc.name }}",
				"is_dynamic_url": 1,
			}
			self.assertRaises(frappe.PermissionError, frappe.get_doc(dynamic).insert)

		with test_user(roles=["System Manager", "Code Author"]) as user, self.set_user(user.name):
			webhook = frappe.get_doc(dynamic).insert()

		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			static_url = {"request_url": "https://example.com/{{ frappe.session.user }}"}
			self.assertTrue(frappe.db.exists("Webhook", {"request_url": static_url["request_url"]}))
			copy = {**dynamic, **static_url, "name": frappe.generate_hash(length=10)}
			self.assertRaises(frappe.PermissionError, frappe.get_doc(copy).insert)

		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			webhook.is_dynamic_url = 0
			webhook.save()

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
			make_notification(condition=f"{self.notification.condition}  ")
			for condition in ("doc.status == 'Closed'", "doc.status == 'OPEN'"):
				with self.subTest(condition=condition):
					self.assertRaises(frappe.PermissionError, make_notification, condition=condition)

			# a JSON value sent already parsed is refused cleanly, not with a query error
			web_form = {
				"doctype": "Web Form",
				"title": frappe.generate_hash(length=10),
				"doc_type": "ToDo",
				"dynamic_filters_json": [["ToDo", "owner", "=", "frappe.session.user"]],
			}
			self.assertRaises(frappe.PermissionError, frappe.get_doc(web_form).insert)

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
			# duplicating it, as the standard notification error suggests, while the database
			# still holds an older message than the app file
			make_notification(message=app_file)

			doc = frappe.get_doc("Notification", self.notification.name)
			doc.run_method("onload")
			doc.enabled = 0
			doc.save()

			doc.message = "{{ frappe.session.user }}"
			self.assertRaises(frappe.PermissionError, doc.save)

		# a new standard notification has no app file yet, so its message is checked as usual
		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			self.assertRaises(
				frappe.PermissionError,
				make_notification,
				is_standard=1,
				module="Email",
				message="{{ frappe.session.user }}",
			)
