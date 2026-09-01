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

	def test_insert_valid_row(self):
		doc = make_blob_doc().insert()

		self.assertTrue(doc.name)
		saved = frappe.get_doc("File Blob", doc.name)
		self.assertEqual(saved.key, f"{TEST_CHECKSUM[:2]}/{TEST_CHECKSUM[2:4]}/{TEST_CHECKSUM}")
		self.assertEqual(saved.checksum, TEST_CHECKSUM)
		self.assertEqual(saved.file_size, 11)
		self.assertEqual(saved.mime_type, "application/octet-stream")
		self.assertEqual(saved.driver, "memory")
		self.assertEqual(saved.is_private, 1)
		self.assertEqual(saved.status, "Ready")

	def test_unique_key_enforced(self):
		make_blob_doc().insert()

		# same (key, is_private, driver) must hit the unique index
		self.assertRaises(frappe.UniqueValidationError, make_blob_doc().insert)

	def test_unique_index_is_scoped_by_privacy_and_driver(self):
		make_blob_doc().insert()

		# the key derives from content alone; the same key may exist once
		# per is_private and per driver
		public_twin = make_blob_doc(is_private=0).insert()
		other_driver_twin = make_blob_doc(driver="local").insert()

		self.assertTrue(public_twin.name)
		self.assertTrue(other_driver_twin.name)

	def test_non_system_manager_cannot_create(self):
		frappe.set_user("Guest")

		self.assertRaises(frappe.PermissionError, make_blob_doc().insert)
