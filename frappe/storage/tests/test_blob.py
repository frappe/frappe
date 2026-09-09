# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import warnings
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.storage import put_blob
from frappe.storage.blob import (
	SPOOL_MAX_MEMORY,
	delete_bytes_on_rollback,
	make_key,
	revive_blob,
	sanitized_extension,
	sha256_of,
	sniff_mime,
	spool_to_tempfile,
	validate_upload,
)
from frappe.storage.driver import BUILTIN_DRIVERS, get_driver, get_driver_classes
from frappe.storage.memory_driver import MemoryDriver, fake
from frappe.storage.tests import reset_file_controller
from frappe.tests import IntegrationTestCase

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@contextmanager
def flag_on():
	"""Enable storage_v2 in site conf for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf["storage_v2"] = 1
	reset_file_controller()
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_v2", None)
		else:
			frappe.conf["storage_v2"] = previous
		reset_file_controller()


@contextmanager
def hooked_drivers(value):
	"""Pretend an app registered `value` under the storage_drivers hook."""
	real_get_hooks = frappe.get_hooks

	def get_hooks(hook=None, *args, **kwargs):
		if hook == "storage_drivers":
			return value
		return real_get_hooks(hook, *args, **kwargs)

	with patch("frappe.get_hooks", side_effect=get_hooks):
		yield


def unique_content(prefix=b"storage-v2-blob-test-"):
	"""Unique bytes per call so dedup never collides across tests or runs."""
	return prefix + frappe.generate_hash(length=32).encode()


class TestPutBlob(IntegrationTestCase):
	def put(self, content: bytes, is_private: bool = False):
		blob = put_blob(io.BytesIO(content), is_private=is_private)
		self.addCleanup(
			frappe.delete_doc, "File Blob", blob.name, force=1, ignore_permissions=True, ignore_missing=True
		)
		return blob

	def test_dedup_returns_same_blob_for_same_bytes_and_privacy(self):
		content = unique_content()
		with fake():
			first = self.put(content, is_private=True)
			second = self.put(content, is_private=True)

			self.assertEqual(first.name, second.name)
			self.assertEqual(frappe.db.count("File Blob", {"checksum": first.checksum, "is_private": 1}), 1)

	def test_public_and_private_get_distinct_blobs(self):
		content = unique_content()
		with fake() as store:
			public = self.put(content, is_private=False)
			private = self.put(content, is_private=True)

			self.assertNotEqual(public.name, private.name)
			# key derives from content alone, so both rows share it
			self.assertEqual(public.key, private.key)
			self.assertEqual(public.is_private, 0)
			self.assertEqual(private.is_private, 1)
			self.assertTrue(store.exists(public.key, is_private=False))
			self.assertTrue(store.exists(private.key, is_private=True))

	def test_checksum_is_sha256_of_content(self):
		content = unique_content()
		with fake():
			blob = self.put(content)
		self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())

	def test_mime_sniffed_from_bytes_not_filename(self):
		# PNG magic bytes are detected even if the client would claim a .txt name
		png = PNG_MAGIC + unique_content(prefix=b"")
		text = unique_content(prefix=b"plain text claimed as a.txt ")
		with fake():
			self.assertEqual(self.put(png).mime_type, "image/png")
			self.assertEqual(self.put(text).mime_type, "application/octet-stream")

	def test_key_layout(self):
		content = unique_content()
		with fake():
			blob = self.put(content)
		checksum = blob.checksum
		self.assertEqual(blob.key, f"{checksum[:2]}/{checksum[2:4]}/{checksum}")
		self.assertEqual(blob.key, make_key(checksum))

	def test_blob_row_fields(self):
		content = unique_content()
		with fake() as store:
			blob = self.put(content, is_private=True)

			self.assertEqual(blob.doctype, "File Blob")
			self.assertEqual(blob.driver, "memory")
			self.assertEqual(blob.file_size, len(content))
			self.assertEqual(blob.status, "Ready")
			self.assertEqual(blob.is_private, 1)
			self.assertTrue(blob.name)

			# bytes actually landed in the driver under the key
			with store.read(blob.key, is_private=True) as stream:
				self.assertEqual(stream.read(), content)

	def test_rolled_back_write_deletes_bytes(self):
		# a rolled-back File Blob row must not leave unreachable bytes behind
		content = unique_content(b"rollback-")
		with fake() as store:
			blob = put_blob(io.BytesIO(content))
			key = blob.key
			self.assertTrue(store.exists(key))

			frappe.db.rollback()

			self.assertFalse(frappe.db.exists("File Blob", blob.name))
			self.assertFalse(store.exists(key))

	def test_validate_upload_rejects_pdf_with_javascript(self):
		# legacy File.check_content parity on the finish_upload path
		pdf = b"%PDF-1.4\n" + unique_content(prefix=b"")
		with fake():
			blob = self.put(pdf)
			self.assertEqual(blob.mime_type, "application/pdf")

			with patch("frappe.utils.pdf.pdf_contains_js", return_value=True):
				self.assertRaises(frappe.ValidationError, validate_upload, blob, "doc.pdf")
			with patch("frappe.utils.pdf.pdf_contains_js", return_value=False):
				validate_upload(blob, "doc.pdf")

	def test_multi_megabyte_stream(self):
		# well past SPOOL_MAX_MEMORY, so the spool spills to disk
		content = unique_content() + b"\x00\xff" * (2 * 1024 * 1024)
		self.assertGreater(len(content), SPOOL_MAX_MEMORY)
		with fake() as store:
			blob = self.put(content, is_private=True)

			self.assertEqual(blob.file_size, len(content))
			self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
			with store.read(blob.key, is_private=True) as stream:
				self.assertEqual(stream.read(), content)


class TestBlobHelpers(IntegrationTestCase):
	def test_spool_spills_large_input_to_disk(self):
		content = b"a" * (SPOOL_MAX_MEMORY + 1)
		spool, size = spool_to_tempfile(io.BytesIO(content))
		with spool:
			self.assertEqual(size, len(content))
			# SpooledTemporaryFile rolled over: content is on disk, not in RAM
			self.assertTrue(spool._rolled)
			self.assertEqual(spool.read(), content)

	def test_spool_keeps_small_input_in_memory(self):
		content = b"small"
		spool, size = spool_to_tempfile(io.BytesIO(content))
		with spool:
			self.assertEqual(size, len(content))
			self.assertFalse(spool._rolled)
			self.assertEqual(spool.read(), content)

	def test_sha256_of_reads_from_start_and_rewinds(self):
		content = b"hello world"
		stream = io.BytesIO(content)
		stream.seek(5)
		self.assertEqual(sha256_of(stream), hashlib.sha256(content).hexdigest())
		self.assertEqual(stream.tell(), 0)

	def test_sniff_mime_rewinds_stream(self):
		stream = io.BytesIO(PNG_MAGIC + b"rest of file")
		self.assertEqual(sniff_mime(stream), "image/png")
		self.assertEqual(stream.tell(), 0)

	def test_sanitized_extension_drops_unusable_extensions(self):
		self.assertEqual(sanitized_extension("report.PDF"), "pdf")
		self.assertEqual(sanitized_extension("archive.tar.gz"), "gz")
		# nothing that looks like an extension
		self.assertEqual(sanitized_extension("README"), "")
		self.assertEqual(sanitized_extension(None), "")
		# unusable: empty, too long, non-ascii, not alphanumeric
		self.assertEqual(sanitized_extension("trailing."), "")
		self.assertEqual(sanitized_extension("a.extensiontoolong"), "")
		self.assertEqual(sanitized_extension("a.pñg"), "")
		self.assertEqual(sanitized_extension("a.p g"), "")

	def test_key_ignores_an_unusable_extension(self):
		content = unique_content(b"bad-extension-")
		with fake():
			blob = put_blob(io.BytesIO(content), filename="evil.p g")
			self.addCleanup(
				frappe.delete_doc,
				"File Blob",
				blob.name,
				force=1,
				ignore_permissions=True,
				ignore_missing=True,
			)
		self.assertEqual(blob.key, make_key(blob.checksum))


class TestReviveBlob(IntegrationTestCase):
	"""revive_blob: the lock taken on a deduped blob before it is relinked."""

	def test_revive_returns_false_when_the_row_vanished(self):
		# garbage collection deleted the row between the dedup lookup and the lock
		with fake():
			blob = put_blob(io.BytesIO(unique_content(b"revive-")))
		frappe.delete_doc("File Blob", blob.name, force=1, ignore_permissions=True)

		self.assertFalse(revive_blob(blob.name))

	def test_revive_locks_an_existing_row(self):
		with fake():
			blob = put_blob(io.BytesIO(unique_content(b"revive-")))
		self.addCleanup(
			frappe.delete_doc, "File Blob", blob.name, force=1, ignore_permissions=True, ignore_missing=True
		)

		self.assertTrue(revive_blob(blob.name))


class TestRollbackCleanup(IntegrationTestCase):
	"""delete_bytes_on_rollback: the after_rollback callback put_blob registers."""

	def test_bytes_owned_by_a_surviving_row_are_kept(self):
		content = unique_content(b"rollback-keep-")
		with fake() as store:
			blob = put_blob(io.BytesIO(content))
			self.addCleanup(
				frappe.delete_doc,
				"File Blob",
				blob.name,
				force=1,
				ignore_permissions=True,
				ignore_missing=True,
			)

			# a File Blob row still points at this key, so the bytes stay
			delete_bytes_on_rollback(store, blob.key, False)()

			self.assertTrue(store.exists(blob.key))
			with store.read(blob.key) as stream:
				self.assertEqual(stream.read(), content)

	def test_driver_failure_is_logged_not_raised(self):
		class BrokenDriver:
			name = "memory"

			def __init__(self):
				self.deleted = []

			def delete(self, key, *, is_private=False):
				self.deleted.append(key)
				raise OSError("driver is down")

		driver = BrokenDriver()
		# no File Blob row owns this key, so the callback tries to delete it
		key = make_key(frappe.generate_hash(length=64))

		with patch("frappe.logger") as logger:
			delete_bytes_on_rollback(driver, key, False)()

		self.assertEqual(driver.deleted, [key])
		logger.assert_called_with("storage")
		self.assertTrue(logger.return_value.warning.called)


class TestDriverRegistry(IntegrationTestCase):
	"""get_driver_classes and get_driver: the storage_drivers hook, unknown names."""

	def forget_driver(self, name):
		"""Drop a driver instance from the per-request cache after the test."""

		def drop():
			getattr(frappe.local, "storage_driver_instances", {}).pop(name, None)

		self.addCleanup(drop)

	def test_hook_registers_a_driver(self):
		path = "frappe.storage.memory_driver.MemoryDriver"
		with hooked_drivers({"hooked_test": [path]}):
			classes = get_driver_classes()
			self.assertEqual(classes["hooked_test"], path)
			# built-in drivers survive the merge
			self.assertEqual(classes["local"], BUILTIN_DRIVERS["local"])

			self.forget_driver("hooked_test")
			self.assertIsInstance(get_driver("hooked_test"), MemoryDriver)

	def test_hook_value_forms_and_last_app_wins(self):
		with hooked_drivers({"hooked_test": ["one.Driver", "two.Driver"]}):
			self.assertEqual(get_driver_classes()["hooked_test"], "two.Driver")
		# a hook set as a plain string, not a list
		with hooked_drivers({"hooked_test": "one.Driver"}):
			self.assertEqual(get_driver_classes()["hooked_test"], "one.Driver")

	def test_hook_can_replace_a_builtin(self):
		with hooked_drivers({"local": ["app.CustomLocalDriver"]}):
			self.assertEqual(get_driver_classes()["local"], "app.CustomLocalDriver")

	def test_unknown_driver_throws(self):
		self.addCleanup(frappe.clear_messages)
		self.forget_driver("no-such-driver")

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

		content = unique_content(b"save-file-duplicate-")
		with flag_on(), fake():
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

		def hooked(name, fallback=None):
			# an app still ships a write_file hook, which v2 ignores
			return (lambda *args, **kwargs: None) if name == "write_file" else fallback

		with (
			patch("frappe.utils.file_manager.get_hook_method", side_effect=hooked),
			warnings.catch_warnings(record=True) as caught,
		):
			warnings.simplefilter("always")
			warn_deprecated_storage_hooks()

		messages = [str(warning.message) for warning in caught]
		self.assertTrue(any("write_file" in message for message in messages), messages)
		self.assertFalse(any("delete_file_data_content" in message for message in messages), messages)

	def test_no_warning_without_legacy_hooks(self):
		from frappe.utils.file_manager import warn_deprecated_storage_hooks

		with (
			patch("frappe.utils.file_manager.get_hook_method", return_value=None),
			warnings.catch_warnings(record=True) as caught,
		):
			warnings.simplefilter("always")
			warn_deprecated_storage_hooks()

		self.assertEqual(caught, [])
