# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from flow.ai.doctype.ai_session_attachment.ai_session_attachment import (
	extract_attachment,
	stage_attachment,
	staged_text,
)


def _file(file_name="note.txt", content="attachment body", **kwargs):
	return frappe.get_doc(
		{"doctype": "File", "file_name": file_name, "content": content, "is_private": 1, **kwargs}
	).insert(ignore_permissions=True)


def _ensure_user(email):
	if frappe.db.exists("User", email):
		return email
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"enabled": 1,
		}
	).insert(ignore_permissions=True)
	return email


class TestExtractAttachment(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_extracts_text_and_metadata(self):
		file_doc = _file(content="attachment body")
		data = extract_attachment(file_doc.name)
		self.assertEqual(data["file"], file_doc.name)
		self.assertEqual(data["file_name"], "note.txt")
		self.assertEqual(data["file_size"], file_doc.file_size)
		self.assertEqual(data["extracted_text"], "attachment body")

	def test_rejects_unsupported_extension(self):
		file_doc = _file(file_name="data.bin", content="x")
		with self.assertRaisesRegex(frappe.ValidationError, "Unsupported file type"):
			extract_attachment(file_doc.name)

	def test_rejects_empty_text(self):
		file_doc = _file(file_name="blank.txt", content="   ")
		with self.assertRaisesRegex(frappe.ValidationError, "No readable text"):
			extract_attachment(file_doc.name)

	def test_rejects_file_not_readable_by_user(self):
		# Owned by Administrator and private: a regular user must not be able to attach it.
		file_doc = _file(content="secret body")
		frappe.set_user(_ensure_user("attach-other@example.com"))
		with self.assertRaises(frappe.PermissionError):
			extract_attachment(file_doc.name)

	def test_owner_can_attach_own_file(self):
		frappe.set_user(_ensure_user("attach-owner@example.com"))
		file_doc = _file(file_name="mine.txt", content="my own notes")
		data = extract_attachment(file_doc.name)
		self.assertEqual(data["extracted_text"], "my own notes")


class TestStageAttachment(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_stage_caches_text_and_returns_chip_metadata(self):
		file_doc = _file(content="staged body")
		chip = stage_attachment(file_doc.name)
		self.assertEqual(set(chip), {"file", "file_name", "file_size"})
		self.assertEqual(chip["file"], file_doc.name)
		self.assertEqual(staged_text(file_doc.name), "staged body")

	def test_staged_text_is_user_scoped(self):
		file_doc = _file(content="staged body")
		stage_attachment(file_doc.name)  # cached under Administrator
		frappe.set_user(_ensure_user("attach-scope@example.com"))
		self.assertIsNone(staged_text(file_doc.name))

	def test_staged_text_missing_returns_none(self):
		self.assertIsNone(staged_text("no-such-file"))
