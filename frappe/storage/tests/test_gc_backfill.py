# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import json
import os
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pypika.queries import Table

import frappe
import frappe.storage
from frappe.database.sqlite.query_parameters import convert_frappe_query_parameters
from frappe.query_builder.utils import get_query_builder, prepare_query
from frappe.storage import backfill, gc
from frappe.storage.blob import other_site_key_criterion, put_blob
from frappe.storage.gc import collect_garbage
from frappe.storage.memory_driver import fake
from frappe.storage.tests import storage_v2, unique_bytes
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, cint, get_files_path, now_datetime


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


def empty_stats():
	return {"blobs_deleted": 0, "bytes_delete_errors": 0, "upload_sessions_expired": 0}


def gc_cutoff():
	return add_to_date(now_datetime(), hours=-gc.MIN_AGE_HOURS)


class FakeBucketClient:
	"""boto3 stand-in holding objects keyed by (bucket, key)."""

	def __init__(self, objects: dict, error: Exception | None = None):
		self.objects = objects
		self.error = error
		self.calls = 0

	def get_paginator(self, name):
		return SimpleNamespace(paginate=self.paginate)

	def paginate(self, Bucket, Prefix):
		self.calls += 1
		yield {
			"Contents": [
				{"Key": key} for bucket, key in self.objects if bucket == Bucket and key.startswith(Prefix)
			]
		}

	def get_object(self, Bucket, Key):
		self.calls += 1
		if self.error:
			raise self.error
		return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}


@contextmanager
def backup_bucket(objects: dict, bucket: str = "files", error: Exception | None = None):
	"""Make the S3 storage driver a fake bucket client, so no test reaches a real bucket."""
	client = FakeBucketClient(objects, error)
	if not hasattr(frappe.local, "storage_driver_instances"):
		frappe.local.storage_driver_instances = {}
	driver = SimpleNamespace(client=client, bucket=bucket)
	with (
		patch.dict(frappe.conf, {"storage_driver_config": {"bucket": bucket}}),
		patch.dict(frappe.local.storage_driver_instances, {"s3": driver}),
	):
		yield client


def index_key(site: str | None = None) -> str:
	"""The key Pilot gives a backup run's File index."""
	site = site or frappe.local.site
	return f"sites/{site}/backups_metadata/20261117_162033-{site.replace('.', '_')}-files-index.json"


def index_body(public=(), private=()) -> bytes:
	"""A File index as Pilot writes it, with one v1 item that has no blob."""

	def items(blobs):
		return [{"name": "f", "file_url": f"/files/{blob}/f", "size": 1, "file_blob": blob} for blob in blobs]

	v1_item = {"name": "v1.txt", "file_url": "/files/v1.txt", "size": 1}
	return json.dumps(
		{"files_index": [*items(public), v1_item], "private_files_index": items(private)}
	).encode()


class TestCollectGarbage(IntegrationTestCase):
	"""GC on orphan blobs. Uses fake() so no bytes touch the site dirs."""

	def setUp(self):
		"""Keep GC off the site's real S3 bucket; a test opts in through backup_bucket()."""
		no_bucket = patch.dict(frappe.conf, {"storage_driver_config": None})
		no_bucket.start()
		self.addCleanup(no_bucket.stop)

	def put(self, content=None):
		with storage_v2():
			blob = put_blob(io.BytesIO(content or unique_bytes()))
		self.addCleanup(
			frappe.delete_doc, "File Blob", blob.name, force=1, ignore_permissions=True, ignore_missing=True
		)
		return blob

	def blob_row(self, blob):
		"""The row shape get_orphan_blobs hands to delete_blob."""
		return frappe._dict(name=blob.name, key=blob.key, driver=blob.driver, is_private=blob.is_private)

	def assert_kept(self, store, *blobs):
		for blob in blobs:
			self.assertTrue(frappe.db.exists("File Blob", blob.name))
			self.assertTrue(store.exists(blob.key))

	def reference_from_todo(self, blob):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "storage gc reference"}).insert()
		self.addCleanup(frappe.db.delete, "ToDo", {"name": todo.name})
		frappe.db.set_value("ToDo", todo.name, "allocated_to", blob.name, update_modified=False)
		return {"doctype": "ToDo", "fieldname": "allocated_to", "issingle": 0}

	def reference_from_single(self, blob):
		fieldname = "storage_gc_blob_reference"
		frappe.db.set_single_value("System Settings", fieldname, blob.name, update_modified=False)
		self.addCleanup(frappe.db.delete, "Singles", {"doctype": "System Settings", "field": fieldname})
		return {"doctype": "System Settings", "fieldname": fieldname, "issingle": 1}

	def test_collects_only_old_unreferenced_blobs_whatever_the_flag(self):
		# blobs created while the flag was on must still be collected after it is off
		for enabled in (True, False):
			with self.subTest(storage_v2=enabled), fake() as store:
				orphan, young, by_file, by_todo, by_single = (self.put() for _ in range(5))
				revived_content = unique_bytes(b"gc-revive-")
				revived = self.put(revived_content)
				for blob in (orphan, revived, by_file, by_todo, by_single):
					backdate(blob.name)
				file_row = insert_file_row(
					file_name="gc-ref.txt", file_url=f"/files/{by_file.name}/file", blob=by_file.name
				)
				self.addCleanup(frappe.db.delete, "File", {"name": file_row.name})
				columns = [
					*gc.blob_reference_columns(),
					self.reference_from_todo(by_todo),
					self.reference_from_single(by_single),
				]
				# put_blob's dedup pulls a selected orphan out of the GC window
				self.assertEqual(self.put(revived_content).name, revived.name)

				with storage_v2(enabled), patch.object(gc, "blob_reference_columns", return_value=columns):
					stats = collect_garbage()

				self.assertGreaterEqual(stats["blobs_deleted"], 1)
				self.assertFalse(frappe.db.exists("File Blob", orphan.name))
				self.assertFalse(store.exists(orphan.key))
				self.assert_kept(store, young, revived, by_file, by_todo, by_single)

	def test_incomplete_reference_discovery_deletes_nothing_and_still_expires_uploads(self):
		cases = {
			"no File Blob table": (
				patch("frappe.database.database.Database.table_exists", return_value=False),
				0,
			),
			"discovery error": (
				patch.object(gc, "blob_reference_columns", side_effect=RuntimeError("metadata unavailable")),
				3,
			),
			"missing referenced table": (
				patch.object(
					gc,
					"blob_reference_columns",
					return_value=[{"doctype": "Missing Blob Reference", "fieldname": "blob", "issingle": 0}],
				),
				2,
			),
		}
		for label, (failure, expired) in cases.items():
			with self.subTest(label), fake() as store:
				blob = self.put()
				backdate(blob.name)

				with (
					failure,
					patch.object(gc, "expire_upload_sessions", return_value=expired),
					patch("frappe.logger", return_value=MagicMock()),
				):
					stats = collect_garbage()

				self.assertEqual(stats, {**empty_stats(), "upload_sessions_expired": expired})
				self.assert_kept(store, blob)

	def old_blobs(self, count):
		blobs = [self.put() for _ in range(count)]
		for blob in blobs:
			backdate(blob.name)
		return blobs

	def assert_deleted(self, store, *blobs):
		for blob in blobs:
			self.assertFalse(frappe.db.exists("File Blob", blob.name))
			self.assertFalse(store.exists(blob.key))

	def rekey(self, store, blob, key):
		"""Store the blob's bytes at ``key`` and point its row there."""
		store.write(key, io.BytesIO(b"rekeyed"), is_private=bool(blob.is_private))
		frappe.db.set_value("File Blob", blob.name, "key", key, update_modified=False)
		blob.key = key

	def test_blobs_under_another_sites_prefix_are_not_collected(self):
		"""A key under another site's prefix belongs to a former name or a restored source site.

		The driver refuses to delete those bytes, so collecting would only drop the row
		that relocation and old backups still need."""
		with fake() as store:
			foreign, own, plain = self.old_blobs(3)
			self.rekey(store, foreign, f"sites/other.example/storage/{foreign.name}/a.txt")
			self.rekey(store, own, f"sites/{frappe.local.site}/storage/{own.name}/a.txt")

			collect_garbage()

			self.assert_kept(store, foreign)
			self.assert_deleted(store, own, plain)

	def test_other_site_check_escapes_like_wildcards(self):
		"""An underscore in this site's name must not match another site's prefix."""
		with fake() as store:
			lookalike, own = self.put(), self.put()
			self.rekey(store, lookalike, f"sites/aXb.example/storage/{lookalike.name}/a.txt")
			self.rekey(store, own, f"sites/a_b.example/storage/{own.name}/a.txt")

		blob = frappe.qb.DocType("File Blob")
		with patch.object(frappe.local, "site", "a_b.example"):
			query = (
				frappe.qb.from_(blob)
				.select(blob.name)
				.where(blob.name.isin([lookalike.name, own.name]))
				.where(other_site_key_criterion(blob))
			)
			matched = query.run(pluck=True)

		self.assertEqual(matched, [lookalike.name])

	def test_other_site_check_works_on_sqlite(self):
		"""SQLite has no default LIKE escape, so the check must not depend on one."""
		keys = {
			"own": "sites/a_b.example/storage/x/a.txt",
			"lookalike": "sites/aXb.example/storage/x/a.txt",
			"other": "sites/other.example/storage/x/a.txt",
			"legacy": "public/abc/x/a.txt",
		}
		blob = Table("blob_check")
		with patch.object(frappe.local, "site", "a_b.example"):
			query = (
				get_query_builder("sqlite")
				.from_(blob)
				.select(blob.label)
				.where(other_site_key_criterion(blob))
				.orderby(blob.label)
			)
			sql, params = prepare_query(query)
		connection = sqlite3.connect(":memory:")
		connection.execute('create table blob_check (label text, "key" text)')
		connection.executemany("insert into blob_check values (?, ?)", keys.items())

		matched = [row[0] for row in connection.execute(*convert_frappe_query_parameters(sql, params))]

		self.assertEqual(matched, ["lookalike", "other"])

	def test_blobs_listed_in_a_backup_index_are_kept(self):
		"""A blob that a backup's File index lists stays, so that backup can still be restored."""
		with fake() as store:
			public, private, orphan = self.old_blobs(3)
			body = index_body(public=[public.name], private=[private.name])
			with backup_bucket({("files", index_key()): body}):
				collect_garbage()

			self.assert_kept(store, public, private)
			self.assert_deleted(store, orphan)

	def test_kept_blobs_do_not_stall_later_batches(self):
		"""Kept blobs are left out by the query, so a batch of them cannot stop the loop early."""
		with fake() as store:
			first, second, orphan = self.old_blobs(3)
			kept = {first.name, second.name}

			found = gc.get_orphan_blobs(gc_cutoff(), 1000, gc.blob_reference_columns(), kept)
			self.assertFalse(kept & {row.name for row in found})
			self.assertIn(orphan.name, {row.name for row in found})

			with backup_bucket({("files", index_key()): index_body(public=sorted(kept))}):
				collect_garbage(batch_size=1)
			self.assert_kept(store, first, second)
			self.assert_deleted(store, orphan)

	def test_only_this_sites_index_files_are_read(self):
		"""Month metadata and other sites' indexes share the bucket but pin nothing here."""
		with fake() as store:
			(blob,) = self.old_blobs(1)
			month_key = f"sites/{frappe.local.site}/backups_metadata/2026-11.json"
			objects = {
				("files", month_key): json.dumps({"20261117_162033": {"files": "x.tar"}}).encode(),
				("files", index_key("other.example.com")): index_body(public=[blob.name]),
			}
			with backup_bucket(objects):
				collect_garbage()

			self.assert_deleted(store, blob)

	def test_an_unreadable_backup_index_deletes_no_blobs(self):
		"""Without a complete set of indexed blobs, GC must fail closed."""
		cases = {
			"read error": ({}, RuntimeError("bucket unreachable")),
			"invalid json": ({"body": b"{not json"}, None),
		}
		for label, (body, error) in cases.items():
			with self.subTest(label), fake() as store:
				(blob,) = self.old_blobs(1)
				objects = {("files", index_key()): body.get("body", index_body())}
				with (
					backup_bucket(objects, error=error),
					patch.object(gc, "expire_upload_sessions", return_value=2),
					patch("frappe.logger", return_value=MagicMock()),
				):
					stats = collect_garbage()

				self.assertEqual(stats, {**empty_stats(), "upload_sessions_expired": 2})
				self.assert_kept(store, blob)

	def test_without_an_s3_bucket_gc_reads_no_index(self):
		"""Sites without S3 storage keep today's GC and make no bucket calls."""
		with fake() as store:
			(blob,) = self.old_blobs(1)
			with (
				backup_bucket({("files", index_key()): index_body(public=[blob.name])}) as client,
				patch.dict(frappe.conf, {"storage_driver_config": None}),
			):
				collect_garbage()

			self.assertEqual(client.calls, 0)
			self.assert_deleted(store, blob)

	def test_runs_without_backups_keep_collecting(self):
		"""A site with no backup indexes yet is not blocked."""
		with fake() as store:
			(blob,) = self.old_blobs(1)
			with backup_bucket({}):
				collect_garbage()

			self.assert_deleted(store, blob)

	def test_index_files_in_another_bucket_do_not_keep_blobs(self):
		"""GC sees only the storage bucket; backups kept elsewhere pin nothing and GC deletes as before."""
		with fake() as store:
			(blob,) = self.old_blobs(1)
			with backup_bucket(
				{("pilot-backups", index_key()): index_body(public=[blob.name])}, bucket="files"
			):
				collect_garbage()

			self.assert_deleted(store, blob)

	def test_failing_upload_sweep_is_logged_and_counts_zero(self):
		with patch.object(gc, "expire_stale_upload_sessions", side_effect=Exception("disk gone")):
			self.assertEqual(gc.expire_upload_sessions(frappe.logger("storage")), 0)

	def test_delete_blob_rechecks_and_reads_the_row_under_its_lock(self):
		logger = frappe.logger("storage")
		with fake() as store:
			with self.subTest("driver delete fails: row kept so the next run retries"):
				blob, stats = self.put(), empty_stats()
				backdate(blob.name)
				with patch.object(store, "delete", side_effect=OSError("driver down")):
					self.assertFalse(gc.delete_blob(self.blob_row(blob), gc_cutoff(), logger, stats))
				self.assertEqual(stats, {**empty_stats(), "bytes_delete_errors": 1})
				self.assert_kept(store, blob)

			with self.subTest("row delete fails: bytes gone, row kept"):
				blob, stats = self.put(), empty_stats()
				backdate(blob.name)
				with patch("frappe.delete_doc", side_effect=Exception("row locked")):
					self.assertFalse(gc.delete_blob(self.blob_row(blob), gc_cutoff(), logger, stats))
				self.assertEqual(stats, empty_stats())
				self.assertTrue(frappe.db.exists("File Blob", blob.name))
				self.assertFalse(store.exists(blob.key))

			with self.subTest("touched after selection, or gone"):
				blob, stats = self.put(), empty_stats()
				gone = frappe._dict(name=frappe.generate_hash(length=20), key="gone", driver=store.name)
				self.assertFalse(gc.delete_blob(self.blob_row(blob), gc_cutoff(), logger, stats))
				self.assertFalse(gc.delete_blob(gone, gc_cutoff(), logger, stats))
				self.assertEqual(stats, empty_stats())
				self.assert_kept(store, blob)

			with self.subTest("relocated after selection: bytes freed at the current location"):
				blob = self.put()
				backdate(blob.name)
				stale = self.blob_row(blob)
				relocated_key = "relocated/" + blob.key
				store.write(relocated_key, io.BytesIO(b"moved"))
				frappe.db.set_value(
					"File Blob",
					blob.name,
					{"key": relocated_key, "driver": store.name},
					update_modified=False,
				)
				self.assertTrue(gc.delete_blob(stale, gc_cutoff(), logger, empty_stats()))
				self.assertFalse(frappe.db.exists("File Blob", blob.name))
				self.assertFalse(store.exists(relocated_key))

	def insert_metadata_row(self, doctype, **values):
		doc = frappe.new_doc(doctype)
		doc.name = "storage-gc-" + frappe.generate_hash(length=16)
		doc.update(values)
		doc.db_insert()
		self.addCleanup(frappe.db.delete, doctype, {"name": doc.name})
		return doc

	def test_discovers_standard_child_custom_property_setter_and_single_links(self):
		fields = {
			doctype: f"gc_blob_{frappe.generate_hash(length=8).lower()}"
			for doctype in ("ToDo", "Role Profile Role", "System Settings", "RQ Job")
		}
		for doctype, fieldname in fields.items():
			self.insert_metadata_row(
				"Custom Field",
				dt=doctype,
				label=fieldname,
				fieldname=fieldname,
				fieldtype="Link",
				options="File Blob",
			)
		self.insert_metadata_row(
			"Property Setter",
			doc_type="ToDo",
			doctype_or_field="DocField",
			field_name="assignment_rule",
			property="options",
			property_type="Data",
			value="File Blob",
		)
		frappe.flags.link_fields = {}
		self.addCleanup(setattr, frappe.flags, "link_fields", {})

		columns = {(c["doctype"], c["fieldname"], c["issingle"]) for c in gc.blob_reference_columns()}

		expected = {
			("File", "blob", 0),
			("ToDo", fields["ToDo"], 0),
			("Role Profile Role", fields["Role Profile Role"], 0),
			("ToDo", "assignment_rule", 0),
			("System Settings", fields["System Settings"], 1),
		}
		self.assertLessEqual(expected, columns)
		# RQ Job is virtual: no table to probe
		self.assertNotIn(("RQ Job", fields["RQ Job"], 0), columns)

	def test_warns_once_for_each_unindexed_reference_column(self):
		logger = MagicMock()
		columns = [
			{"doctype": "Indexed Reference", "fieldname": "blob", "issingle": 0},
			{"doctype": "Unindexed Reference", "fieldname": "blob", "issingle": 0},
			{"doctype": "Single Reference", "fieldname": "blob", "issingle": 1},
		]
		with patch.object(
			frappe.db,
			"get_column_index",
			side_effect=[{"Key_name": "blob_index"}, None, None],
		):
			gc._warn_unindexed_reference_columns(columns, logger)

		logger.warning.assert_called_once_with(
			"storage gc: unindexed File Blob reference Unindexed Reference.blob"
		)

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
		frappe.db.delete("File Blob", {"key": ("like", f"{self.prefix}%")})
		super().tearDown()

	def run_backfill(self, **kwargs):
		"""Run backfill on this test's rows only, leaving the keyset filter on name alone."""
		return backfill.run(filters=[["file_name", "like", self.prefix + "%"]], **kwargs)

	def make_legacy_file(self, content=None, is_private=False, content_hash=None, create_bytes=True):
		"""A pre-v2 File row: file on disk, content_hash set, blob NULL."""
		content = content if content is not None else unique_bytes(b"backfill-")
		filename = f"{self.prefix}-{frappe.generate_hash(length=10)}.txt"
		path = get_files_path(filename, is_private=is_private)
		if create_bytes:
			with open(path, "wb") as f:
				f.write(content)
			self.addCleanup(lambda p=path: os.path.exists(p) and os.remove(p))
		file_url = ("/private/files/" if is_private else "/files/") + filename
		return self.insert_legacy_row(file_url, is_private, content_hash or frappe.generate_hash(length=16))

	def insert_legacy_row(self, file_url, is_private=False, content_hash=None):
		"""A legacy File row with an arbitrary file_url and no bytes of its own."""
		return insert_file_row(
			name=self.prefix + frappe.generate_hash(length=10),
			file_name=file_url.rsplit("/", 1)[-1],
			file_url=file_url,
			is_private=cint(is_private),
			is_folder=0,
			content_hash=content_hash,
		)

	def blob_of(self, doc):
		return frappe.db.get_value("File", doc.name, "blob")

	def read_local(self, key):
		with frappe.storage.get_driver("local").read(key) as stream:
			return stream.read()

	def test_links_legacy_rows_in_place_and_skips_bad_ones(self):
		content = unique_bytes(b"backfill-link-")
		public = self.make_legacy_file(content)
		private = self.make_legacy_file(is_private=True)
		missing = self.make_legacy_file(create_bytes=False)
		escaping = self.insert_legacy_row(f"/files/../{self.prefix}-escape.txt")

		stats = self.run_backfill(batch_size=1)

		self.assertEqual((stats["linked"], stats["blobs_created"]), (2, 2))
		skipped = {entry["name"]: entry for entry in stats["skipped"]}
		self.assertEqual(skipped.keys(), {missing.name, escaping.name})
		self.assertEqual(
			skipped[escaping.name],
			{
				"name": escaping.name,
				"file_url": escaping.file_url,
				"reason": "file_url is not a local files path",
			},
		)
		self.assertIsNone(self.blob_of(missing))
		self.assertIsNone(self.blob_of(escaping))

		self.assertEqual(frappe.db.get_value("File", public.name, "file_url"), public.file_url)
		blob = frappe.get_doc("File Blob", self.blob_of(public))
		self.assertEqual(
			(blob.key, blob.checksum, blob.driver, blob.status, blob.is_private, blob.file_size),
			(public.file_name, hashlib.sha256(content).hexdigest(), "local", "Ready", 0, len(content)),
		)
		private_blob = frappe.get_doc("File Blob", self.blob_of(private))
		self.assertEqual((private_blob.key, private_blob.is_private), (private.file_name, 1))

		# bytes stay at the legacy path, and the local driver resolves the key to it
		legacy_path = os.path.realpath(get_files_path(public.file_name))
		self.assertTrue(os.path.isfile(legacy_path))
		self.assertEqual(os.path.realpath(frappe.storage.get_driver("local").get_path(blob.key)), legacy_path)
		self.assertEqual(self.read_local(blob.key), content)

	def test_each_path_gets_its_own_blob_that_gc_can_free(self):
		content = unique_bytes(b"backfill-twins-")
		first = self.make_legacy_file(content)
		twin = self.make_legacy_file(content)
		# legacy content_hash is MD5 and can be stale: never group on it
		other_content = unique_bytes(b"backfill-collide-")
		other = self.make_legacy_file(other_content, content_hash=first.content_hash)

		stats = self.run_backfill()

		self.assertEqual(stats["blobs_created"], 3)
		rows = (first, twin, other)
		blobs = [frappe.get_doc("File Blob", self.blob_of(row)) for row in rows]
		self.assertEqual([blob.key for blob in blobs], [row.file_name for row in rows])
		self.assertEqual(blobs[2].checksum, hashlib.sha256(other_content).hexdigest())
		self.assertEqual([self.read_local(blob.key) for blob in blobs], [content, content, other_content])

		frappe.db.delete("File", {"name": ("in", [row.name for row in rows])})
		for blob in blobs:
			backdate(blob.name)
			self.assertTrue(gc.delete_blob(blob, gc_cutoff(), frappe.logger("storage"), empty_stats()))
		for row in rows:
			self.assertFalse(os.path.exists(get_files_path(row.file_name)))

	def test_rows_at_one_path_share_a_blob_across_reruns(self):
		legacy = self.make_legacy_file()
		twin = self.insert_legacy_row(legacy.file_url)

		first = self.run_backfill()
		blob_name = self.blob_of(legacy)
		second = self.run_backfill()
		late = self.insert_legacy_row(legacy.file_url)
		third = self.run_backfill()

		self.assertEqual((first["linked"], first["blobs_created"]), (2, 1))
		self.assertEqual((second["linked"], second["blobs_created"]), (0, 0))
		self.assertEqual((third["linked"], third["blobs_created"]), (1, 0))
		self.assertEqual({self.blob_of(row) for row in (legacy, twin, late)}, {blob_name})
		self.assertEqual(frappe.db.count("File Blob", {"key": ("like", f"{self.prefix}%")}), 1)

	def test_a_name_filter_keeps_paging_past_a_skipped_row(self):
		missing = self.make_legacy_file(create_bytes=False)
		stats = backfill.run(filters=[["name", "=", missing.name]], batch_size=1)
		self.assertEqual([entry["name"] for entry in stats["skipped"]], [missing.name])

	def test_locate_rejects_remote_and_escaping_urls(self):
		self.assertIsNone(backfill.locate("https://cdn.example.com/logo.png"))
		self.assertIsNone(backfill.locate("/assets/frappe/images/logo.png"))
		self.assertIsNone(backfill.locate("/files/"))
		self.assertIsNone(backfill.locate("/files/../secrets.txt"))
		self.assertIsNone(backfill.locate("/private/files/a/../../secrets.txt"))
		self.assertEqual(backfill.locate("/files/logo.png"), (False, "logo.png"))
		self.assertEqual(backfill.locate("/private/files/a/b.png"), (True, "a/b.png"))


class TestFilesIndex(IntegrationTestCase):
	def test_lists_stored_files_by_privacy_with_their_blobs(self):
		from frappe.core.doctype.file.utils import get_files_index

		tag = frappe.generate_hash(length=10)
		public = insert_file_row(
			file_name=f"public-{tag}.txt", file_url=f"/files/public-{tag}.txt", file_size=3
		)
		private = insert_file_row(
			file_name=f"private-{tag}.txt",
			file_url=f"/private/files/private-{tag}.txt",
			file_size=5,
			is_private=1,
		)
		insert_file_row(file_name=f"folder-{tag}", is_folder=1)
		insert_file_row(file_name=f"link-{tag}.png", file_url=f"https://example.com/link-{tag}.png")
		with fake(), storage_v2():
			stored = frappe.get_doc(
				doctype="File", file_name=f"blob-{tag}.txt", content=unique_bytes(), is_private=1
			).insert()

		index = get_files_index()

		listed = {group: [item for item in items if tag in item["name"]] for group, items in index.items()}
		self.assertEqual(
			listed["files_index"], [{"name": public.file_name, "file_url": public.file_url, "size": 3}]
		)
		self.assertCountEqual(
			listed["private_files_index"],
			[
				{"name": private.file_name, "file_url": private.file_url, "size": 5},
				{
					"name": stored.file_name,
					"file_url": stored.file_url,
					"size": stored.file_size,
					"file_blob": stored.blob,
				},
			],
		)
