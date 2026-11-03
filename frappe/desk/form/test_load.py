# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.form.load import get_filtered_attachments, get_user_info_for_viewers
from frappe.tests.utils import FrappeTestCase


class TestLoad(FrappeTestCase):
	def test_get_user_info_for_viewers_accepts_native_list(self):
		# users as a native list instead of a JSON string (frappe.parse_json passthrough)
		info = get_user_info_for_viewers(["Administrator"])
		self.assertIn("Administrator", info)

	def test_get_user_info_for_viewers_denies_website_users(self):
		from frappe.core.doctype.user_type.test_user_type import create_role

		create_role()
		custom_type = frappe.get_doc(
			doctype="User Type", name="Viewer Test Type", role="_Test User Type"
		).insert()
		self.addCleanup(frappe.delete_doc, "User Type", custom_type.name, force=True)

		def make_user(email, user_type):
			return frappe.get_doc(
				doctype="User", email=email, first_name="Viewer", user_type=user_type, send_welcome_email=0
			).insert(ignore_permissions=True)

		website_user = make_user("viewer_portal@example.com", "Website User")
		custom_user = make_user("viewer_custom@example.com", custom_type.name)
		self.addCleanup(frappe.set_user, "Administrator")

		for desk_user in ("test@example.com", custom_user.name):
			frappe.set_user(desk_user)
			info = get_user_info_for_viewers([website_user.name])
			self.assertEqual(info[website_user.name].fullname, "Viewer")

		frappe.set_user(website_user.name)
		self.assertRaises(frappe.PermissionError, get_user_info_for_viewers, ["test@example.com"])

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
