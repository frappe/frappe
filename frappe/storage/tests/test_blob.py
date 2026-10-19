# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import tempfile
import warnings
from unittest.mock import patch

import frappe
from frappe.storage import put_blob
from frappe.storage.blob import (
	SPOOL_MAX_MEMORY,
	delete_bytes_on_rollback,
	key_filename,
	revive_blob,
	sha256_of,
	sniff_mime,
	spool_to_tempfile,
	validate_upload,
)
from frappe.storage.driver import BUILTIN_DRIVERS, get_driver, get_driver_classes
from frappe.storage.memory_driver import MemoryDriver, fake
from frappe.storage.tests import PNG_MAGIC, hook_value, storage_v2, unique_bytes, unique_png, use_driver
from frappe.tests import IntegrationTestCase


def delete_blob(name: str):
	frappe.delete_doc("File Blob", name, force=1, ignore_permissions=True, ignore_missing=True)


class TestPutBlob(IntegrationTestCase):
	def put(self, content: bytes, is_private: bool = False, filename: str | None = None):
		blob = put_blob(io.BytesIO(content), is_private=is_private, filename=filename)
		self.addCleanup(delete_blob, blob.name)
		return blob

	def test_same_content_and_privacy_reuses_one_blob(self):
		content = unique_bytes()
		with fake() as store:
			first = self.put(content, is_private=True, filename="first.txt")
			second = self.put(content, is_private=True, filename="second.txt")
			public = self.put(content, is_private=False)

			# the reused blob keeps the first filename
			self.assertEqual(second.name, first.name)
			self.assertEqual(second.key, f"{first.name}/first.txt")
			self.assertEqual(frappe.db.count("File Blob", {"checksum": first.checksum, "is_private": 1}), 1)

			self.assertEqual(first.doctype, "File Blob")
			self.assertEqual(first.driver, "memory")
			self.assertEqual(first.file_size, len(content))
			self.assertEqual(first.status, "Ready")
			self.assertEqual(first.checksum, hashlib.sha256(content).hexdigest())
			with store.read(first.key, is_private=True) as stream:
				self.assertEqual(stream.read(), content)

			# the same bytes stored publicly get their own blob and key
			self.assertNotEqual(public.name, first.name)
			self.assertEqual((public.is_private, first.is_private), (0, 1))
			self.assertEqual(public.key, f"{public.name}/file")
			self.assertTrue(store.exists(public.key, is_private=False))

	def test_concurrent_identical_uploads_both_succeed(self):
		# another request stored the same content after this one's reuse lookup
		content = unique_bytes(b"race-")
		real_get_value = frappe.db.get_value

		def lookup_misses(doctype, filters=None, *args, **kwargs):
			if doctype == "File Blob" and isinstance(filters, dict) and "checksum" in filters:
				return None
			return real_get_value(doctype, filters, *args, **kwargs)

		with fake() as store:
			first = self.put(content, filename="first.txt")
			with patch.object(frappe.db, "get_value", side_effect=lookup_misses):
				second = self.put(content, filename="second.txt")

			self.assertNotEqual(second.name, first.name)
			self.assertEqual(frappe.db.count("File Blob", {"checksum": first.checksum}), 2)
			for blob in (first, second):
				with store.read(blob.key) as stream:
					self.assertEqual(stream.read(), content)

	def test_key_is_blob_name_and_safe_filename(self):
		cases = (
			("Report Q1.PDF", "Report Q1.PDF"),
			# path separators and URL delimiters cannot split the key or the URL
			("../a/b\\c?d#e%f.png", "_a_b_c_d_e_f.png"),
			("bell\x07\nname.txt", "bellname.txt"),
			(None, "file"),
			("...", "file"),
		)
		with fake():
			for filename, stored in cases:
				with self.subTest(filename=filename):
					blob = self.put(unique_bytes(), filename=filename)
					self.assertEqual(blob.key, f"{blob.name}/{stored}")
		# a long name is cut to 200 bytes and keeps its extension
		self.assertEqual(key_filename("x" * 300 + ".tar.gz"), "x" * 197 + ".gz")

	def test_long_unicode_filename_is_stored_on_local_disk(self):
		# 90 CJK characters are 270 UTF-8 bytes, over a filesystem's 255-byte name limit
		from frappe.storage.tests.test_serve_upload import TempLocalDriver

		content = unique_bytes()
		with tempfile.TemporaryDirectory() as root, use_driver(TempLocalDriver(root)) as driver:
			blob = self.put(content, filename="报" * 90 + ".txt")

			stored_name = blob.key.rsplit("/", 1)[1]
			self.assertTrue(stored_name.startswith("报"))
			self.assertTrue(stored_name.endswith(".txt"))
			with driver.read(blob.key) as stream:
				self.assertEqual(stream.read(), content)

	def test_mime_is_sniffed_from_bytes_not_filename(self):
		with fake():
			self.assertEqual(self.put(unique_png(), filename="a.txt").mime_type, "image/png")
			self.assertEqual(self.put(unique_bytes(b"plain text ")).mime_type, "application/octet-stream")

	def test_validate_upload_rejects_pdf_with_javascript(self):
		# legacy File.check_content parity on the upload session finish path
		with fake():
			blob = self.put(unique_bytes(b"%PDF-1.4\n"))
			self.assertEqual(blob.mime_type, "application/pdf")

			with patch("frappe.utils.pdf.pdf_contains_js", return_value=True):
				self.assertRaises(frappe.ValidationError, validate_upload, blob, "doc.pdf")
			with patch("frappe.utils.pdf.pdf_contains_js", return_value=False):
				validate_upload(blob, "doc.pdf")

	def test_large_stream_spills_to_disk_and_round_trips(self):
		for size, on_disk in ((5, False), (SPOOL_MAX_MEMORY + 1, True)):
			with self.subTest(size=size):
				spool, spooled_size = spool_to_tempfile(io.BytesIO(b"a" * size))
				with spool:
					self.assertEqual(spooled_size, size)
					self.assertEqual(spool._rolled, on_disk)
					self.assertEqual(spool.read(), b"a" * size)

		content = unique_bytes() + b"\x00\xff" * (2 * 1024 * 1024)
		with fake() as store:
			blob = self.put(content, is_private=True)

			self.assertEqual(blob.file_size, len(content))
			self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
			with store.read(blob.key, is_private=True) as stream:
				self.assertEqual(stream.read(), content)

	def test_hashing_and_sniffing_rewind_the_stream(self):
		stream = io.BytesIO(PNG_MAGIC + b"rest of file")
		stream.seek(5)
		self.assertEqual(sha256_of(stream), hashlib.sha256(PNG_MAGIC + b"rest of file").hexdigest())
		self.assertEqual(stream.tell(), 0)
		self.assertEqual(sniff_mime(stream), "image/png")
		self.assertEqual(stream.tell(), 0)


class TestBlobLifecycle(IntegrationTestCase):
	"""revive_blob before relinking a reused blob; byte cleanup after a rollback."""

	def test_revive_locks_an_existing_row_and_misses_a_deleted_one(self):
		with fake():
			blob = put_blob(io.BytesIO(unique_bytes(b"revive-")))
		self.addCleanup(delete_blob, blob.name)
		self.assertTrue(revive_blob(blob.name))

		# garbage collection deleted the row between the reuse lookup and the lock
		delete_blob(blob.name)
		self.assertFalse(revive_blob(blob.name))

	def test_rollback_deletes_bytes_only_when_no_row_owns_them(self):
		content = unique_bytes(b"rollback-")
		with fake() as store:
			blob = put_blob(io.BytesIO(content))
			self.addCleanup(delete_blob, blob.name)

			# a File Blob row still points at this key, so the bytes stay
			delete_bytes_on_rollback(store, blob.key, False)()
			with store.read(blob.key) as stream:
				self.assertEqual(stream.read(), content)

			frappe.db.rollback()

			self.assertFalse(frappe.db.exists("File Blob", blob.name))
			self.assertFalse(store.exists(blob.key))

	def test_rollback_cleanup_logs_driver_failure(self):
		class BrokenDriver:
			name = "memory"

			def __init__(self):
				self.deleted = []

			def delete(self, key, *, is_private=False):
				self.deleted.append(key)
				raise OSError("driver is down")

		driver = BrokenDriver()
		key = f"{frappe.generate_hash(length=10)}/orphan.txt"

		with patch("frappe.logger") as logger:
			delete_bytes_on_rollback(driver, key, False)()

		self.assertEqual(driver.deleted, [key])
		logger.assert_called_with("storage")
		self.assertTrue(logger.return_value.warning.called)


class TestDriverRegistry(IntegrationTestCase):
	"""get_driver_classes and get_driver: the storage_drivers hook, unknown names."""

	def setUp(self):
		super().setUp()
		for name in ("hooked_test", "no-such-driver"):
			self.addCleanup(
				lambda name=name: getattr(frappe.local, "storage_driver_instances", {}).pop(name, None)
			)

	def test_storage_drivers_hook_adds_and_replaces_drivers(self):
		path = "frappe.storage.memory_driver.MemoryDriver"
		with hook_value("storage_drivers", {"hooked_test": [path]}):
			self.assertEqual(get_driver_classes()["hooked_test"], path)
			self.assertEqual(get_driver_classes()["local"], BUILTIN_DRIVERS["local"])
			self.assertIsInstance(get_driver("hooked_test"), MemoryDriver)

		cases = (
			# the last app wins
			({"hooked_test": ["one.Driver", "two.Driver"]}, "hooked_test", "two.Driver"),
			({"hooked_test": "one.Driver"}, "hooked_test", "one.Driver"),
			({"local": ["app.CustomLocalDriver"]}, "local", "app.CustomLocalDriver"),
		)
		for hooked, name, expected in cases:
			with self.subTest(hooked=hooked), hook_value("storage_drivers", hooked):
				self.assertEqual(get_driver_classes()[name], expected)

	def test_unknown_driver_throws(self):
		self.addCleanup(frappe.clear_messages)

		with self.assertRaises(frappe.ValidationError) as caught:
			get_driver("no-such-driver")

		self.assertIn("Unknown storage driver", str(caught.exception))
		self.assertNotIn("no-such-driver", getattr(frappe.local, "storage_driver_instances", {}))


class TestFileManagerSaveFile(IntegrationTestCase):
	"""frappe.utils.file_manager.save_file on the storage v2 branch."""

	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	def test_duplicate_insert_returns_the_existing_file(self):
		"""A racing insert returns the row that won, instead of failing.

		File names are hashes, so the collision is simulated: only the
		DuplicateEntryError handling is under test."""
		from frappe.core.doctype.file.file_v2 import FileV2
		from frappe.utils.file_manager import save_file

		content = unique_bytes(b"save-file-duplicate-")
		with storage_v2(), fake():
			existing = save_file("duplicate.txt", content, None, None, is_private=1)

			def duplicate_insert(doc, *args, **kwargs):
				doc.duplicate_entry = existing.name
				raise frappe.DuplicateEntryError("File", existing.name)

			with patch.object(FileV2, "insert", duplicate_insert):
				returned = save_file("duplicate.txt", content, None, None, is_private=1)

		self.assertEqual(returned.name, existing.name)
		self.assertEqual(returned.doctype, "File")

	def test_legacy_byte_hooks_warn_on_the_v2_path(self):
		from frappe.utils.file_manager import warn_deprecated_storage_hooks

		def write_file_hooked(name, fallback=None):
			# an app still ships a write_file hook, which v2 ignores
			return (lambda *args, **kwargs: None) if name == "write_file" else fallback

		for get_hook_method, warned in ((write_file_hooked, ["write_file"]), (lambda *args: None, [])):
			with (
				self.subTest(warned=warned),
				patch("frappe.utils.file_manager.get_hook_method", side_effect=get_hook_method),
				warnings.catch_warnings(record=True) as caught,
			):
				warnings.simplefilter("always")
				warn_deprecated_storage_hooks()
				self.assertEqual(len(caught), len(warned))
				for hook, warning in zip(warned, caught, strict=True):
					self.assertIn(hook, str(warning.message))
