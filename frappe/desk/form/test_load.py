# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.core.doctype.communication.communication import parse_email
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.form.load import (
	add_comments,
	get_document_email,
	get_filtered_attachments,
	get_user_info_for_viewers,
)
from frappe.tests import IntegrationTestCase


class TestLoad(IntegrationTestCase):
	def test_get_user_info_for_viewers_accepts_native_list(self):
		# users as a native list instead of a JSON string (frappe.parse_json passthrough)
		info = get_user_info_for_viewers(["Administrator"])
		self.assertIn("Administrator", info)

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

	def test_get_document_email(self):
		with patch(
			"frappe.email.doctype.email_account.email_account.get_automatic_email_link",
			return_value="erpnext@example.com",
		):
			address = get_document_email("Purchase Order", "PO-26465-002")
			address_with_separator_in_name = get_document_email("Purchase Order", "PO/2026/002")

		self.assertEqual(address, "erpnext+Purchase%20Order=PO-26465-002@example.com")
		self.assertEqual(
			address_with_separator_in_name, "erpnext+Purchase%20Order=PO%2F2026%2F002@example.com"
		)
		self.assertEqual([("Purchase Order", "PO-26465-002")], list(parse_email([address])))
		self.assertEqual(
			[("Purchase Order", "PO/2026/002")], list(parse_email([address_with_separator_in_name]))
		)
