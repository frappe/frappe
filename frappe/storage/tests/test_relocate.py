# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
from unittest.mock import MagicMock, patch

import frappe
from frappe.storage import gc, relocate
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

	def insert_blob(self, content: bytes, key: str | None = None, driver=None):
		driver = driver or self.source
		name = self.prefix + frappe.generate_hash(length=6)
		key = (key or f"legacy/{name}.txt").format(name=name)
		driver.write(key, io.BytesIO(content))
		blob = frappe.new_doc("File Blob")
		blob.name = name
		blob.update(
			{
				"key": key,
				"checksum": hashlib.sha256(content).hexdigest(),
				"file_size": len(content),
				"mime_type": "application/octet-stream",
				"driver": driver.name,
				"is_private": 0,
				"status": "Ready",
			}
		)
		blob.db_insert()
		return blob

	def insert_file(self, blob, file_url: str):
		file_doc = frappe.new_doc("File")
		file_doc.name = self.prefix + "-file" + frappe.generate_hash(length=6)
		file_doc.update(
			{
				"file_name": file_url.rsplit("/", 1)[-1],
				"file_url": file_url,
				"blob": blob.name,
				"is_folder": 0,
			}
		)
		file_doc.db_insert()
		return file_doc

	def location(self, blob):
		return frappe.db.get_value("File Blob", blob.name, ["driver", "key"], as_dict=True)

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

	def run_relocation(self, commit=None, **kwargs):
		with (
			patch.object(relocate, "get_relocation_batch", side_effect=self.scoped_batch),
			patch.object(relocate, "get_driver", side_effect=self.driver_for),
			patch.object(relocate, "_commit_batch", side_effect=commit or frappe.db.after_commit.run),
		):
			return relocate.relocate_blobs(**kwargs)

	def test_moves_bytes_to_configured_driver_and_keeps_the_old_url(self):
		content = b"relocation-configured-driver"
		blob = self.insert_blob(content, key="legacy/{name}/report.pdf")
		file_doc = self.insert_file(blob, "/files/legacy/report.pdf")
		# a driver shared by several sites puts each site's keys under a prefix
		self.target.key_prefix = "site-a/"

		stats = self.run_relocation()

		canonical_key = f"site-a/{blob.name}/report.pdf"
		self.assertEqual(stats, {"moved": 1, "bytes": len(content), "skipped": 0, "errors": 0})
		self.assertEqual(self.location(blob), {"driver": self.target.name, "key": canonical_key})
		self.assertEqual(self.target.read(canonical_key).read(), content)
		self.assertFalse(self.source.exists(blob.key))
		# the v1 URL stays; it is served from the blob wherever it lives
		self.assertEqual(frappe.db.get_value("File", file_doc.name, "file_url"), "/files/legacy/report.pdf")

	def test_moves_local_in_place_key_on_same_driver(self):
		self.source.name = "local"
		self.target = self.source
		content = b"same-driver-in-place"
		blob = self.insert_blob(content, key=f"{self.prefix}.txt")

		stats = self.run_relocation(target_driver="local")

		canonical_key = f"{blob.name}/{self.prefix}.txt"
		self.assertEqual(stats["moved"], 1)
		self.assertEqual(self.location(blob).key, canonical_key)
		self.assertEqual(self.target.read(canonical_key).read(), content)
		self.assertFalse(self.source.exists(blob.key))

	def test_failures_keep_the_source_and_the_run_continues(self):
		unreadable = self.insert_blob(b"driver-error")
		lost = self.insert_blob(b"relocation-lost-copy")
		good_content = b"driver-continues"
		good = self.insert_blob(good_content)  # moves, but the after-commit cleanup fails
		real_read, real_write = self.source.read, self.target.write

		def flaky_read(key, *, is_private=False):
			if key == unreadable.key:
				raise OSError("source unavailable")
			return real_read(key, is_private=is_private)

		def lossy_write(key, stream, *, is_private=False):
			if not key.startswith(lost.name):
				real_write(key, stream, is_private=is_private)

		logger = MagicMock()
		with (
			patch.object(self.source, "read", side_effect=flaky_read),
			patch.object(self.target, "write", side_effect=lossy_write),
			patch.object(frappe.db, "exists", side_effect=OSError("database unavailable")),
			patch("frappe.storage.relocate.frappe.logger", return_value=logger),
		):
			stats = self.run_relocation()

		self.assertEqual(stats, {"moved": 1, "bytes": len(good_content), "skipped": 0, "errors": 3})
		for blob in (unreadable, lost):
			self.assertEqual(self.location(blob), {"driver": self.source.name, "key": blob.key})
			self.assertTrue(self.source.exists(blob.key))
		self.assertEqual(self.location(good).driver, self.target.name)
		self.assertTrue(self.source.exists(good.key))
		self.assertEqual(logger.warning.call_count, 3)

	def test_interrupted_batch_resumes_and_moves_the_rest(self):
		first = self.insert_blob(b"resume-first")
		second = self.insert_blob(b"resume-second")
		first, second = sorted((first, second), key=lambda blob: blob.name)

		def interrupt_after_commit():
			frappe.db.after_commit.run()
			raise KeyboardInterrupt

		with self.assertRaises(KeyboardInterrupt):
			self.run_relocation(commit=interrupt_after_commit, batch_size=1)

		self.assertEqual(
			(self.location(first).driver, self.location(second).driver), (self.target.name, self.source.name)
		)

		stats = self.run_relocation(batch_size=1)

		self.assertEqual(stats, {"moved": 1, "bytes": second.file_size, "skipped": 1, "errors": 0})
		self.assertEqual(self.location(second).driver, self.target.name)

	def test_reuses_objects_already_at_the_target(self):
		canonical = self.insert_blob(b"already-canonical", key="{name}/canonical.txt", driver=self.target)
		existing_content = b"existing-target-object"
		existing = self.insert_blob(existing_content, key="legacy/existing.txt")
		self.target.write(f"{existing.name}/existing.txt", io.BytesIO(existing_content))
		same_content = b"same-content-on-both-drivers"
		twin = self.insert_blob(same_content, key="{name}/same.txt", driver=self.target)
		blob = self.insert_blob(same_content, key="legacy/same.txt")

		with (
			patch.object(self.target, "write", wraps=self.target.write) as write,
			patch.object(self.target, "delete", wraps=self.target.delete) as delete,
		):
			stats = self.run_relocation(target_driver=self.target.name)

		moved_bytes = len(existing_content) + len(same_content)
		self.assertEqual(stats, {"moved": 2, "bytes": moved_bytes, "skipped": 2, "errors": 0})
		# only the blob whose own canonical object is missing gets written
		self.assertEqual([call.args[0] for call in write.call_args_list], [f"{blob.name}/same.txt"])
		delete.assert_not_called()
		self.assertEqual(self.target.read(canonical.key).read(), b"already-canonical")
		self.assertEqual(self.target.read(twin.key).read(), same_content)
		self.assertEqual(self.target.read(f"{blob.name}/same.txt").read(), same_content)
		self.assertEqual(frappe.db.count("File Blob", {"checksum": existing.checksum}), 1)
		for moved in (existing, blob):
			self.assertEqual(self.location(moved).driver, self.target.name)
			self.assertFalse(self.source.exists(moved.key))

	def test_gc_racing_a_copy_keeps_a_live_blob_and_drops_a_deleted_ones_copy(self):
		live = self.insert_blob(b"gc-live-relocation")
		file_doc = self.insert_file(live, "/files/relocation.txt")
		frappe.db.set_value(
			"File Blob", live.name, "modified", add_to_date(now_datetime(), hours=-48), update_modified=False
		)
		gone = self.insert_blob(b"gc-deleted-during-relocation", key="legacy/{name}/gone.txt")
		gone_key = f"{gone.name}/gone.txt"
		candidate = frappe._dict(name=live.name, key=live.key, driver=live.driver, is_private=live.is_private)
		gc_stats = {}
		real_write = self.target.write

		def write_during_gc(key, stream, *, is_private=False):
			real_write(key, stream, is_private=is_private)
			if key.startswith(live.name):
				with patch.object(gc, "get_orphan_blobs", return_value=[candidate]):
					gc_stats.update(gc.collect_garbage())
			else:
				frappe.db.delete("File Blob", {"name": gone.name})

		with patch.object(self.target, "write", side_effect=write_during_gc) as write:
			stats = self.run_relocation()

		self.assertEqual((stats["moved"], stats["skipped"]), (1, 1))
		self.assertEqual(gc_stats["blobs_deleted"], 0)
		self.assertTrue(frappe.db.exists("File Blob", live.name))
		self.assertEqual(frappe.db.get_value("File", file_doc.name, "blob"), live.name)
		self.assertIn(gone_key, [call.args[0] for call in write.call_args_list])
		self.assertFalse(self.target.exists(gone_key))

	def test_rejects_nonpositive_batch_size(self):
		for batch_size in (0, -1):
			self.assertRaises(frappe.ValidationError, relocate.relocate_blobs, batch_size)
