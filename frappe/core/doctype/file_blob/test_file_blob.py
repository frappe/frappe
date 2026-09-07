# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe.database.schema import get_definition
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


class TestFileBlobSize(IntegrationTestCase):
	"""`file_size` must describe an object of any size the driver can hold.

	An S3 object goes up to 5 TB and the Drive migration copies such objects
	into blobs, so a signed 32-bit column is too narrow: a strict `sql_mode`
	refuses the insert and a permissive one clamps the value, which would
	then lie to ranged serving, to relocation, and to every byte count.

	The field is `Int` with `length: 20`. Schema sync promotes that to the
	`Long Int` column type (`frappe/database/schema.py:437`), which is the
	declaration `File.file_size` already carries.

	Every size below is declared. No bytes are written.
	"""

	ABOVE_INT32 = 2**31  # one byte past a signed int(11)
	ABOVE_5GB = 5 * 1024**3 + 1  # one byte past the S3 single-part copy limit

	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	def test_the_field_is_declared_as_a_bigint(self):
		field = frappe.get_meta("File Blob").get_field("file_size")

		self.assertEqual(field.fieldtype, "Int")
		# Pinned against the type map, not against a literal, so the test
		# holds on every backend the framework builds a schema for.
		self.assertEqual(get_definition("Int", length=field.length), get_definition("Long Int"))

	def test_a_size_above_the_signed_int_ceiling_round_trips(self):
		doc = make_blob_doc(file_size=self.ABOVE_INT32).insert()

		self.assertEqual(frappe.db.get_value("File Blob", doc.name, "file_size"), self.ABOVE_INT32)

	def test_a_size_above_five_gb_round_trips(self):
		doc = make_blob_doc(file_size=self.ABOVE_5GB).insert()

		# Through the database and through the document, since a clamp on
		# either side would be invisible to the other.
		self.assertEqual(frappe.db.get_value("File Blob", doc.name, "file_size"), self.ABOVE_5GB)
		self.assertEqual(frappe.get_doc("File Blob", doc.name).file_size, self.ABOVE_5GB)

	def test_a_size_above_the_bigint_ceiling_is_still_refused(self):
		# The column is wider, not unbounded. A number no column can hold is
		# still a validation error, not a silent truncation.
		self.assertRaises(frappe.CharacterLengthExceededError, make_blob_doc(file_size=2**63).insert)
