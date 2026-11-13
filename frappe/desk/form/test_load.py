# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.core.doctype.module_def.module_def import get_installed_apps as get_module_installed_apps
from frappe.desk.form.load import get_filtered_attachments, get_user_info_for_viewers, getdoctype
from frappe.tests.utils import FrappeTestCase
from frappe.utils.change_log import get_versions


class TestLoad(FrappeTestCase):
	def test_get_user_info_for_viewers_accepts_native_list(self):
		# users as a native list instead of a JSON string (frappe.parse_json passthrough)
		info = get_user_info_for_viewers(["Administrator"])
		self.assertIn("Administrator", info)

	def test_desk_meta_endpoints_require_desk_user(self):
		from frappe.core.doctype.user_type.test_user_type import create_role

		create_role()
		custom_type = frappe.get_doc(
			doctype="User Type", name="Meta Test Type", role="_Test User Type"
		).insert()
		self.addCleanup(frappe.delete_doc, "User Type", custom_type.name, force=True)

		users = {}
		for key, user_type in (("website", "Website User"), ("custom", custom_type.name)):
			users[key] = frappe.get_doc(
				doctype="User", email=f"meta_{key}@example.com", first_name="Meta", user_type=user_type
			).insert(ignore_permissions=True, ignore_mandatory=True)
			self.addCleanup(frappe.delete_doc, "User", users[key].name, force=True)
		self.addCleanup(frappe.set_user, "Administrator")
		endpoints = (
			lambda: getdoctype("Role"),
			get_versions,
			get_module_installed_apps,
		)

		frappe.set_user(users["website"].name)
		for endpoint in endpoints:
			self.assertRaises(frappe.PermissionError, endpoint)

		frappe.local.response = frappe._dict(docs=[])
		for desk_user in ("test@example.com", users["custom"].name):
			frappe.set_user(desk_user)
			for endpoint in endpoints:
				endpoint()
		self.assertEqual(frappe.response.docs[0]["name"], "Role")

	def test_get_filtered_attachments(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Attachment filter test"}).insert()
		other_todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "Other attachment filter test"}
		).insert()
		matching_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_invoice.pdf",
				"file_url": "https://example.com/test_invoice.pdf",
				"attached_to_doctype": todo.doctype,
				"attached_to_name": todo.name,
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "other_invoice.pdf",
				"file_url": "https://example.com/other_invoice.pdf",
				"attached_to_doctype": todo.doctype,
				"attached_to_name": todo.name,
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_other.pdf",
				"file_url": "https://example.com/test_other.pdf",
				"attached_to_doctype": other_todo.doctype,
				"attached_to_name": other_todo.name,
			}
		).insert()

		attachments = get_filtered_attachments(
			todo.doctype,
			todo.name,
			json.dumps([["File", "file_name", "like", "test_%"]]),
		)

		self.assertEqual([attachment.name for attachment in attachments], [matching_file.name])

	def test_get_filtered_attachments_rejects_structured_field_and_operator(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Attachment filter type test"}).insert()

		with self.assertRaises(frappe.ValidationError):
			get_filtered_attachments(
				todo.doctype,
				todo.name,
				json.dumps([["File", ["file_name", "like", "x"], "=", "x"]]),
			)

		with self.assertRaises(frappe.ValidationError):
			get_filtered_attachments(
				todo.doctype,
				todo.name,
				json.dumps([["File", "file_name", ["like", "x"], "x"]]),
			)
