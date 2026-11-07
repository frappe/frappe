# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase

TEST_CHECKSUM = "ab" * 32  # 64 hex chars, sha256-shaped


def make_blob_doc(**overrides):
	doc = frappe.new_doc("File Blob")
	doc.update(
		{
			"key": f"{TEST_CHECKSUM[:2]}/{TEST_CHECKSUM[2:4]}/{TEST_CHECKSUM}",
			"checksum": TEST_CHECKSUM,
			"file_size": 11,
			"mime_type": "application/octet-stream",
			"driver": "memory",
			"is_private": 1,
			"status": "Ready",
		}
	)
	doc.update(overrides)
	return doc


class TestFileBlob(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDown()

	def test_rows_store_their_fields_and_same_content_may_have_several(self):
		# dedup is a best-effort lookup; concurrent uploads may store twins
		first = make_blob_doc().insert()
		second = make_blob_doc(key="second").insert()

		self.assertNotEqual(first.name, second.name)
		self.assertEqual(frappe.db.count("File Blob", {"checksum": TEST_CHECKSUM}), 2)
		saved = frappe.get_doc("File Blob", first.name)
		self.assertEqual(
			(saved.key, saved.checksum, saved.file_size, saved.mime_type, saved.driver, saved.is_private),
			(make_blob_doc().key, TEST_CHECKSUM, 11, "application/octet-stream", "memory", 1),
		)
		self.assertEqual(saved.status, "Ready")

	def test_non_system_manager_cannot_create(self):
		frappe.set_user("Guest")

		self.assertRaises(frappe.PermissionError, make_blob_doc().insert)

	def test_file_size_holds_objects_larger_than_a_32_bit_column(self):
		# S3 objects reach 5 TB, so a clamped size would lie to ranged serving and relocation
		for size in (2**31, 5 * 1024**3 + 1):
			with self.subTest(size=size):
				doc = make_blob_doc(file_size=size).insert()

				self.assertEqual(frappe.db.get_value("File Blob", doc.name, "file_size"), size)
				self.assertEqual(frappe.get_doc("File Blob", doc.name).file_size, size)

		# wider, not unbounded: a size no column can hold is refused, not truncated
		self.assertRaises(frappe.CharacterLengthExceededError, make_blob_doc(file_size=2**63).insert)
