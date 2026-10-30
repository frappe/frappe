# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
<<<<<<< HEAD
from frappe.desk.form.load import get_filtered_attachments, get_user_info_for_viewers
from frappe.tests.utils import FrappeTestCase
=======
from frappe.core.doctype.communication.communication import parse_email
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.core.doctype.module_def.module_def import get_installed_apps as get_module_installed_apps
from frappe.desk.desktop import get_installed_apps
from frappe.desk.form.load import (
	add_comments,
	get_document_email,
	get_filtered_attachments,
	get_user_info_for_viewers,
	getdoctype,
)
from frappe.tests import IntegrationTestCase
from frappe.utils.change_log import get_versions
>>>>>>> d1c87ed (fix: limit desk metadata endpoints to desk users)


class TestLoad(FrappeTestCase):
	def test_get_user_info_for_viewers_accepts_native_list(self):
		# users as a native list instead of a JSON string (frappe.parse_json passthrough)
		info = get_user_info_for_viewers(["Administrator"])
		self.assertIn("Administrator", info)

<<<<<<< HEAD
=======
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
			get_installed_apps,
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

	def test_add_comments_hides_attachment_activity_for_restricted_fields(self):
		doctype = new_doctype(
			fields=[
				{"label": "Open Attach", "fieldname": "open_attach", "fieldtype": "Attach", "permlevel": 0},
				{
					"label": "Restricted Attach",
					"fieldname": "restricted_attach",
					"fieldtype": "Attach",
					"permlevel": 1,
				},
			],
			permissions=[
				{"role": "System Manager", "read": 1, "write": 1, "create": 1, "permlevel": 0},
				{"role": "System Manager", "read": 1, "write": 1, "permlevel": 1},
				{"role": "All", "read": 1, "write": 1, "create": 1, "permlevel": 0},
			],
		).insert(ignore_if_duplicate=True)

		doc = frappe.get_doc(doctype=doctype.name).insert(ignore_permissions=True)

		def attach(fieldname):
			return frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"{fieldname}.txt",
					"content": fieldname,
					"attached_to_doctype": doctype.name,
					"attached_to_name": doc.name,
					"attached_to_field": fieldname,
				}
			).insert(ignore_permissions=True)

		open_file = attach("open_attach")
		restricted_file = attach("restricted_attach")

		def attachment_log_names():
			out = frappe._dict()
			add_comments(frappe.get_doc(doctype.name, doc.name), out)
			return {c.content for c in out.attachment_logs}

		frappe.set_user("test4@example.com")
		try:
			restricted_logs = attachment_log_names()
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(any(open_file.file_name in c for c in restricted_logs))
		self.assertFalse(any(restricted_file.file_name in c for c in restricted_logs))

		full_logs = attachment_log_names()
		self.assertTrue(any(open_file.file_name in c for c in full_logs))
		self.assertTrue(any(restricted_file.file_name in c for c in full_logs))

>>>>>>> d1c87ed (fix: limit desk metadata endpoints to desk users)
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
