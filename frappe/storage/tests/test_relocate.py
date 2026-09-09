# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
from unittest.mock import MagicMock, patch

import frappe
from frappe.storage import gc, relocate
from frappe.storage.blob import make_key
from frappe.storage.memory_driver import MemoryDriver
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime


class NamedMemoryDriver(MemoryDriver):
	def __init__(self, name: str):
		super().__init__()
		self.name = name


class TestRelocateBlobs(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.prefix = "relocate" + frappe.generate_hash(length=8)
		self.source = NamedMemoryDriver("relocate-source")
		self.target = NamedMemoryDriver("relocate-target")

	def tearDown(self):
		frappe.db.delete("File", {"name": ("like", self.prefix + "%")})
		frappe.db.delete("File Blob", {"name": ("like", self.prefix + "%")})
		super().tearDown()

	def insert_blob(self, content: bytes, *, suffix: str = "", key: str | None = None, driver=None):
		driver = driver or self.source
		checksum = hashlib.sha256(content).hexdigest()
		key = key or f"legacy/{self.prefix}{suffix}"
		driver.write(key, io.BytesIO(content))
		blob = frappe.new_doc("File Blob")
		blob.name = self.prefix + suffix + frappe.generate_hash(length=6)
		blob.update(
			{
				"key": key,
				"checksum": checksum,
				"file_size": len(content),
				"mime_type": "application/octet-stream",
				"driver": driver.name,
				"is_private": 0,
				"status": "Ready",
			}
		)
		blob.db_insert()
		return blob

	def scoped_batch(self, limit: int, after_name: str):
		return frappe.get_all(
			"File Blob",
			filters=[["name", "like", self.prefix + "%"], ["name", ">", after_name]],
			fields=["name", "key", "checksum", "file_size", "driver", "is_private"],
			order_by="name asc",
			limit=limit,
		)

	def driver_for(self, name=None):
		if name in (None, self.target.name):
			return self.target
		if name == self.source.name:
			return self.source
		raise AssertionError(f"unexpected driver {name}")

	def commit_callbacks(self):
		frappe.db.after_commit.run()

	def run_relocation(self, **kwargs):
		with (
			patch.object(relocate, "get_relocation_batch", side_effect=self.scoped_batch),
			patch.object(relocate, "get_driver", side_effect=self.driver_for),
			patch.object(relocate, "_commit_batch", side_effect=self.commit_callbacks),
		):
			return relocate.relocate_blobs(**kwargs)

	def test_moves_bytes_to_configured_driver_and_deletes_source_after_commit(self):
		content = b"relocation-configured-driver"
		blob = self.insert_blob(content)
		old_key = blob.key

		stats = self.run_relocation()

		canonical_key = make_key(blob.checksum)
		self.assertEqual(stats, {"moved": 1, "bytes": len(content), "skipped": 0, "errors": 0})
		self.assertEqual(
			frappe.db.get_value("File Blob", blob.name, ["driver", "key"], as_dict=True),
			{"driver": self.target.name, "key": canonical_key},
		)
		self.assertEqual(self.target.read(canonical_key).read(), content)
		self.assertFalse(self.source.exists(old_key))

	def test_moves_local_in_place_key_on_same_driver(self):
		self.source.name = "local"
		self.target = self.source
		content = b"same-driver-in-place"
		blob = self.insert_blob(content, key=f"../{self.prefix}.txt")
		old_key = blob.key

		stats = self.run_relocation(target_driver="local")

		self.assertEqual(stats["moved"], 1)
		self.assertEqual(frappe.db.get_value("File Blob", blob.name, "key"), make_key(blob.checksum))
		self.assertEqual(self.target.read(make_key(blob.checksum)).read(), content)
		self.assertFalse(self.source.exists(old_key))

	def test_interrupted_batch_resumes_and_moves_the_rest(self):
		first = self.insert_blob(b"resume-first", suffix="-a-")
		second = self.insert_blob(b"resume-second", suffix="-b-")
		commits = 0

		def interrupt_after_commit():
			nonlocal commits
			commits += 1
			self.commit_callbacks()
			if commits == 1:
				raise KeyboardInterrupt

		with (
			patch.object(relocate, "get_relocation_batch", side_effect=self.scoped_batch),
			patch.object(relocate, "get_driver", side_effect=self.driver_for),
			patch.object(relocate, "_commit_batch", side_effect=interrupt_after_commit),
			self.assertRaises(KeyboardInterrupt),
		):
			relocate.relocate_blobs(batch_size=1)

		moved_driver = frappe.db.get_value("File Blob", first.name, "driver")
		remaining_driver = frappe.db.get_value("File Blob", second.name, "driver")
		self.assertEqual((moved_driver, remaining_driver), (self.target.name, self.source.name))

		stats = self.run_relocation(batch_size=1)

		self.assertEqual(stats, {"moved": 1, "bytes": len(b"resume-second"), "skipped": 1, "errors": 0})
		self.assertEqual(frappe.db.get_value("File Blob", second.name, "driver"), self.target.name)

	def test_blob_at_canonical_target_is_untouched(self):
		content = b"already-canonical"
		checksum = hashlib.sha256(content).hexdigest()
		blob = self.insert_blob(content, key=make_key(checksum), driver=self.target)

		with (
			patch.object(self.target, "write", wraps=self.target.write) as write,
			patch.object(self.target, "delete", wraps=self.target.delete) as delete,
		):
			stats = self.run_relocation(target_driver=self.target.name)

		self.assertEqual(stats, {"moved": 0, "bytes": 0, "skipped": 1, "errors": 0})
		write.assert_not_called()
		delete.assert_not_called()
		self.assertTrue(self.target.exists(blob.key))

	def test_existing_target_object_is_reused_without_a_duplicate_blob(self):
		content = b"existing-target-object"
		blob = self.insert_blob(content)
		canonical_key = make_key(blob.checksum)
		self.target.write(canonical_key, io.BytesIO(content))

		with patch.object(self.target, "write", wraps=self.target.write) as write:
			stats = self.run_relocation(target_driver=self.target.name)

		self.assertEqual(stats["moved"], 1)
		write.assert_not_called()
		self.assertEqual(frappe.db.count("File Blob", {"checksum": blob.checksum}), 1)
		self.assertEqual(frappe.db.get_value("File Blob", blob.name, "driver"), self.target.name)

	def test_driver_error_is_logged_and_next_blob_continues(self):
		bad = self.insert_blob(b"driver-error", suffix="-a-")
		good_content = b"driver-continues"
		good = self.insert_blob(good_content, suffix="-b-")
		real_read = self.source.read

		def flaky_read(key, *, is_private=False):
			if key == bad.key:
				raise OSError("source unavailable")
			return real_read(key, is_private=is_private)

		logger = MagicMock()
		with (
			patch.object(self.source, "read", side_effect=flaky_read),
			patch("frappe.storage.relocate.frappe.logger", return_value=logger),
		):
			stats = self.run_relocation()

		self.assertEqual(stats, {"moved": 1, "bytes": len(good_content), "skipped": 0, "errors": 1})
		self.assertEqual(frappe.db.get_value("File Blob", bad.name, "driver"), self.source.name)
		self.assertEqual(frappe.db.get_value("File Blob", good.name, "driver"), self.target.name)
		self.assertTrue(logger.warning.called)

	def test_after_commit_cleanup_error_is_logged_and_does_not_abort(self):
		content = b"cleanup-query-error"
		blob = self.insert_blob(content)
		old_key = blob.key
		logger = MagicMock()

		with (
			patch.object(frappe.db, "exists", side_effect=OSError("database unavailable")),
			patch("frappe.storage.relocate.frappe.logger", return_value=logger),
		):
			stats = self.run_relocation()

		self.assertEqual(stats, {"moved": 1, "bytes": len(content), "skipped": 0, "errors": 1})
		self.assertEqual(frappe.db.get_value("File Blob", blob.name, "driver"), self.target.name)
		self.assertTrue(self.source.exists(old_key))
		logger.warning.assert_called_once()

	def test_gc_interleaved_with_copy_keeps_a_live_blob(self):
		content = b"gc-live-relocation"
		blob = self.insert_blob(content)
		file_doc = frappe.new_doc("File")
		file_doc.name = self.prefix + "-file"
		file_doc.update(
			{
				"file_name": "relocation.txt",
				"file_url": "/files/relocation.txt",
				"blob": blob.name,
				"is_folder": 0,
			}
		)
		file_doc.db_insert()
		frappe.db.set_value(
			"File Blob",
			blob.name,
			"modified",
			add_to_date(now_datetime(), hours=-48),
			update_modified=False,
		)
		candidate = frappe._dict(
			name=blob.name,
			key=blob.key,
			driver=blob.driver,
			is_private=blob.is_private,
		)
		gc_stats = None
		real_write = self.target.write

		def write_during_gc(key, stream, *, is_private=False):
			nonlocal gc_stats
			real_write(key, stream, is_private=is_private)
			with patch.object(gc, "get_orphan_blobs", return_value=[candidate]):
				gc_stats = gc.collect_garbage()

		with patch.object(self.target, "write", side_effect=write_during_gc):
			stats = self.run_relocation()

		self.assertEqual(stats["moved"], 1)
		self.assertEqual(gc_stats["blobs_deleted"], 0)
		self.assertTrue(frappe.db.exists("File Blob", blob.name))
		self.assertEqual(frappe.db.get_value("File", file_doc.name, "blob"), blob.name)

	def test_rejects_nonpositive_batch_size(self):
		for batch_size in (0, -1):
			self.assertRaises(frappe.ValidationError, relocate.relocate_blobs, batch_size)
