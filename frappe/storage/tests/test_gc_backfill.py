# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import os
from contextlib import contextmanager

import frappe
import frappe.storage
from frappe.storage import backfill
from frappe.storage.blob import put_blob
from frappe.storage.gc import collect_garbage
from frappe.storage.memory_driver import fake
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, cint, get_files_path, now_datetime


@contextmanager
def flag_on():
	"""Enable storage_v2 in site conf for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf["storage_v2"] = 1
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_v2", None)
		else:
			frappe.conf["storage_v2"] = previous


def unique_content(prefix=b"storage-v2-gc-test-"):
	return prefix + frappe.generate_hash(length=32).encode()


def backdate(blob_name, hours=48):
	frappe.db.set_value(
		"File Blob",
		blob_name,
		"modified",
		add_to_date(now_datetime(), hours=-hours),
		update_modified=False,
	)


def insert_file_row(**values):
	"""Insert a bare File row with no doc events (legacy-style fixture)."""
	doc = frappe.new_doc("File")
	doc.update(values)
	doc.name = values.get("name") or frappe.generate_hash(length=10)
	doc.owner = doc.modified_by = "Administrator"
	doc.creation = doc.modified = now_datetime()
	doc.db_insert()
	return doc


class TestCollectGarbage(IntegrationTestCase):
	"""GC on orphan blobs. Uses fake() so no bytes touch the site dirs."""

	def put(self, content=None, is_private=False):
		blob = put_blob(io.BytesIO(content or unique_content()), is_private=is_private)
		self.addCleanup(
			frappe.delete_doc, "File Blob", blob.name, force=1, ignore_permissions=True, ignore_missing=True
		)
		return blob

	def test_deletes_old_orphan_blob_and_bytes(self):
		with flag_on(), fake() as store:
			blob = self.put()
			backdate(blob.name)
			self.assertTrue(store.exists(blob.key))

			stats = collect_garbage()

			self.assertFalse(frappe.db.exists("File Blob", blob.name))
			self.assertFalse(store.exists(blob.key))
			self.assertGreaterEqual(stats["blobs_deleted"], 1)

	def test_keeps_referenced_blob(self):
		with flag_on(), fake() as store:
			blob = self.put()
			file_row = insert_file_row(
				file_name="gc-ref.txt",
				file_url=f"/files/blobs/{blob.key}",
				blob=blob.name,
			)
			self.addCleanup(frappe.db.delete, "File", {"name": file_row.name})
			backdate(blob.name)

			collect_garbage()

			self.assertTrue(frappe.db.exists("File Blob", blob.name))
			self.assertTrue(store.exists(blob.key))

	def test_keeps_young_orphan_blob(self):
		with flag_on(), fake() as store:
			blob = self.put()

			collect_garbage()

			self.assertTrue(frappe.db.exists("File Blob", blob.name))
			self.assertTrue(store.exists(blob.key))

	def test_collects_orphans_even_when_flag_off(self):
		# turning the flag off must not strand orphans created while it was on
		with fake() as store:
			with flag_on():
				blob = self.put()
			backdate(blob.name)
			self.assertFalse(frappe.storage.enabled())

			stats = collect_garbage()

			self.assertGreaterEqual(stats["blobs_deleted"], 1)
			self.assertFalse(frappe.db.exists("File Blob", blob.name))
			self.assertFalse(store.exists(blob.key))

	def test_revived_orphan_survives_collection(self):
		# put_blob's dedup pulls a selected orphan out of the GC window
		with flag_on(), fake() as store:
			content = unique_content(b"gc-revive-")
			blob = self.put(content)
			backdate(blob.name)

			revived = put_blob(io.BytesIO(content))
			self.assertEqual(revived.name, blob.name)

			collect_garbage()

			self.assertTrue(frappe.db.exists("File Blob", blob.name))
			self.assertTrue(store.exists(blob.key))

	def test_gc_is_registered_as_daily_scheduler_event(self):
		daily = frappe.get_hooks("scheduler_events").get("daily", [])
		self.assertIn("frappe.storage.gc.collect_garbage", daily)


class TestBackfill(IntegrationTestCase):
	"""Backfill on synthetic legacy File rows with real files on disk."""

	def setUp(self):
		super().setUp()
		self.prefix = "bfut" + frappe.generate_hash(length=8)

	def tearDown(self):
		frappe.db.delete("File", {"name": ("like", self.prefix + "%")})
		frappe.db.delete("File Blob", {"key": ("like", f"../{self.prefix}%")})
		super().tearDown()

	def filters(self):
		"""Scope backfill.run to this test's rows only."""
		return {"name": ("like", self.prefix + "%")}

	def make_legacy_file(self, content=None, is_private=False, content_hash=None, create_bytes=True):
		"""A pre-v2 File row: file on disk, content_hash set, blob NULL."""
		content = content if content is not None else unique_content(b"backfill-")
		filename = f"{self.prefix}-{frappe.generate_hash(length=10)}.txt"
		path = get_files_path(filename, is_private=is_private)
		if create_bytes:
			with open(path, "wb") as f:
				f.write(content)
			self.addCleanup(lambda p=path: os.path.exists(p) and os.remove(p))
		file_url = ("/private/files/" if is_private else "/files/") + filename
		return insert_file_row(
			name=self.prefix + frappe.generate_hash(length=10),
			file_name=filename,
			file_url=file_url,
			is_private=cint(is_private),
			is_folder=0,
			content_hash=content_hash or frappe.generate_hash(length=16),
		)

	def reload(self, doc):
		return frappe.db.get_value(
			"File", doc.name, ["name", "blob", "file_url", "content_hash"], as_dict=True
		)

	def test_backfill_creates_blob_at_legacy_key_and_links_rows(self):
		content = unique_content(b"backfill-link-")
		public = self.make_legacy_file(content)
		private = self.make_legacy_file(is_private=True)

		stats = backfill.run(batch_size=1, filters=self.filters())

		self.assertEqual(stats["linked"], 2)
		self.assertEqual(stats["blobs_created"], 2)
		self.assertEqual(stats["skipped"], [])

		row = self.reload(public)
		self.assertTrue(row.blob)
		self.assertEqual(row.file_url, public.file_url)  # file_url untouched
		blob = frappe.get_doc("File Blob", row.blob)
		self.assertEqual(blob.key, f"../{public.file_name}")
		self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
		self.assertEqual(blob.driver, "local")
		self.assertEqual(blob.status, "Ready")
		self.assertEqual(blob.is_private, 0)
		self.assertEqual(blob.file_size, len(content))

		private_blob = frappe.get_doc("File Blob", self.reload(private).blob)
		self.assertEqual(private_blob.is_private, 1)
		self.assertEqual(private_blob.key, f"../{private.file_name}")

	def test_bytes_stay_at_legacy_path_and_driver_resolves_them(self):
		content = unique_content(b"backfill-bytes-")
		legacy = self.make_legacy_file(content)
		legacy_path = os.path.realpath(get_files_path(legacy.file_name))

		backfill.run(filters=self.filters())

		self.assertTrue(os.path.isfile(legacy_path))  # not moved
		blob = frappe.get_doc("File Blob", self.reload(legacy).blob)
		driver = frappe.storage.get_driver("local")
		self.assertEqual(os.path.realpath(driver.get_path(blob.key)), legacy_path)
		self.assertTrue(driver.exists(blob.key))
		with driver.read(blob.key) as stream:
			self.assertEqual(stream.read(), content)

	def test_same_hash_rows_share_one_blob(self):
		content = unique_content(b"backfill-dedup-")
		content_hash = frappe.generate_hash(length=16)
		first = self.make_legacy_file(content, content_hash=content_hash)
		second = self.make_legacy_file(content, content_hash=content_hash)

		stats = backfill.run(filters=self.filters())

		self.assertEqual(stats["blobs_created"], 1)
		self.assertEqual(stats["linked"], 2)
		first_blob = self.reload(first).blob
		self.assertTrue(first_blob)
		self.assertEqual(self.reload(second).blob, first_blob)

	def test_missing_disk_file_is_skipped_and_logged(self):
		missing = self.make_legacy_file(create_bytes=False)
		fine = self.make_legacy_file()

		stats = backfill.run(filters=self.filters())

		self.assertIsNone(self.reload(missing).blob)
		self.assertTrue(self.reload(fine).blob)
		skipped_names = [s["name"] for s in stats["skipped"]]
		self.assertIn(missing.name, skipped_names)
		self.assertEqual(len(stats["skipped"]), 1)

	def test_second_run_is_idempotent(self):
		legacy = self.make_legacy_file()

		first = backfill.run(filters=self.filters())
		blob_name = self.reload(legacy).blob

		second = backfill.run(filters=self.filters())

		self.assertEqual(first["linked"], 1)
		self.assertEqual(second["linked"], 0)
		self.assertEqual(second["blobs_created"], 0)
		self.assertEqual(self.reload(legacy).blob, blob_name)
		self.assertEqual(
			frappe.db.count("File Blob", {"key": ("like", f"../{self.prefix}%")}), 1
		)
