# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import threading
import time
from unittest.mock import MagicMock, patch

import frappe
from frappe.patches.v17_0 import migrate_s3_blob_keys
from frappe.storage import gc, relocate
from frappe.storage.blob import other_site_key_criterion
from frappe.storage.memory_driver import MemoryDriver
from frappe.storage.tests.test_s3_driver import StubClientError, make_driver
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

	def insert_blob(self, content: bytes, key: str | None = None, driver=None, is_private: bool = False):
		driver = driver or self.source
		name = self.prefix + frappe.generate_hash(length=6)
		key = (key or f"legacy/{name}.txt").format(name=name)
		driver.write(key, io.BytesIO(content), is_private=is_private)
		blob = frappe.new_doc("File Blob")
		blob.name = name
		blob.update(
			{
				"key": key,
				"checksum": hashlib.sha256(content).hexdigest(),
				"file_size": len(content),
				"mime_type": "application/octet-stream",
				"driver": driver.name,
				"is_private": int(is_private),
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

	def scoped_batch(
		self, limit: int, after_name: str, source_driver: str | None = None, from_other_sites: bool = False
	):
		"""get_relocation_batch limited to this test's rows."""
		blob = frappe.qb.DocType("File Blob")
		query = (
			frappe.qb.from_(blob)
			.select(blob.name, blob.key, blob.checksum, blob.file_size, blob.driver, blob.is_private)
			.where(blob.name.like(self.prefix + "%"))
			.where(blob.name > after_name)
			.orderby(blob.name)
			.limit(limit)
		)
		if source_driver is not None:
			query = query.where(blob.driver == source_driver)
		if from_other_sites:
			query = query.where(other_site_key_criterion(blob))
		return query.run(as_dict=True)

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

	def s3_driver(self, bucket="test-bucket"):
		driver = make_driver(bucket=bucket, prefix="old-site")
		client = driver.test_client
		objects = {}

		def head_object(Bucket, Key):
			if (Bucket, Key) not in objects:
				raise StubClientError("404")
			return {"ContentLength": len(objects[(Bucket, Key)])}

		client.head_object.side_effect = head_object
		client.upload_fileobj.side_effect = lambda stream, bucket, key: objects.__setitem__(
			(bucket, key), stream.read()
		)
		client.get_object.side_effect = lambda Bucket, Key: {"Body": io.BytesIO(objects[(Bucket, Key)])}
		client.copy.side_effect = lambda CopySource, Bucket, Key: objects.__setitem__(
			(Bucket, Key), objects[(CopySource["Bucket"], CopySource["Key"])]
		)
		client.delete_object.side_effect = lambda Bucket, Key: objects.pop((Bucket, Key), None)
		return driver

	def run_renamed_relocation(self, driver):
		with (
			patch.object(relocate, "get_relocation_batch", side_effect=self.scoped_batch),
			patch.object(relocate, "get_driver", return_value=driver),
			patch.object(relocate, "_commit_batch", side_effect=frappe.db.after_commit.run),
		):
			return relocate.relocate_renamed_site_blobs()

	def renamed_blob(self, s3, content: bytes = b"renamed"):
		"""A blob still stored under the site's former name."""
		return self.insert_blob(content, key="sites/old.example/storage/{name}/a.txt", driver=s3)

	def own_key(self, blob) -> str:
		return f"sites/{frappe.local.site}/storage/{blob.name}/a.txt"

	def test_s3_copy_requires_the_same_client_and_bucket(self):
		with self.set_user("testperm@example.com"):
			for bucket, same_client, native_copy in (
				("test-bucket", True, True),
				("other-bucket", True, False),
				("test-bucket", False, False),
			):
				with self.subTest(bucket=bucket, same_client=same_client):
					source = self.s3_driver()
					target = self.s3_driver(bucket=bucket)
					if same_client:
						target.client = source.client
					blob = self.insert_blob(
						b"copy-conditions", key="old-site/{name}/report.txt", driver=source
					)
					source.client.reset_mock()
					target.client.reset_mock()
					with patch.object(relocate, "get_driver", return_value=source):
						plan = relocate.plan_relocation(blob, target)
					relocate.copy_blob(plan)
					relocate.repoint_blob(plan, {"errors": 0}, MagicMock())
					if native_copy:
						target.client.copy.assert_called_once()
						source.client.get_object.assert_not_called()
						target.client.upload_fileobj.assert_not_called()
					else:
						source.client.copy.assert_not_called()
						target.client.copy.assert_not_called()
						source.client.get_object.assert_called_once()
						target.client.upload_fileobj.assert_called_once()
					self.assertEqual(target.read(self.location(blob).key).read(), b"copy-conditions")
					frappe.db.after_commit.run()

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

	def test_source_driver_filter_leaves_other_drivers_untouched(self):
		with self.set_user("testperm@example.com"):
			blob = self.insert_blob(b"filtered-source")
			other = self.insert_blob(b"filtered-other", driver=self.target)
			with (
				patch.object(relocate, "get_driver", side_effect=self.driver_for),
				patch.object(relocate, "_commit_batch", side_effect=frappe.db.after_commit.run),
			):
				stats = relocate.relocate_blobs(source_driver=self.source.name, batch_size=1)
			self.assertEqual(stats, {"moved": 1, "bytes": blob.file_size, "skipped": 0, "errors": 0})
			self.assertEqual(self.location(blob).driver, self.target.name)
			self.assertEqual(self.location(other).key, other.key)
			self.assertTrue(self.target.exists(other.key))

	def test_s3_key_patch_preserves_urls_and_local_blobs_and_can_be_repeated(self):
		with self.set_user("testperm@example.com"):
			self.source = self.target = self.s3_driver()
			blob = self.insert_blob(b"legacy-s3", key="old-site/{name}/report.pdf")
			private = self.insert_blob(b"private-s3", key="old-site/{name}/private.txt", is_private=True)
			file_doc = self.insert_file(blob, f"/files/{blob.name}/report.pdf")
			local_driver = NamedMemoryDriver("local")
			local = self.insert_blob(b"keep-local", driver=local_driver)
			client = self.target.test_client
			client.upload_fileobj.reset_mock()
			with (
				patch.object(relocate, "get_relocation_batch", side_effect=self.scoped_batch),
				patch.object(relocate, "get_driver", side_effect=self.driver_for),
				patch.object(relocate, "_commit_batch", side_effect=frappe.db.after_commit.run),
			):
				migrate_s3_blob_keys.execute()
				migrate_s3_blob_keys.execute()
			client.get_object.assert_not_called()
			client.upload_fileobj.assert_not_called()
			self.assertEqual(client.copy.call_count, 2)
			for old_blob in (blob, private):
				is_private = bool(old_blob.is_private)
				client.copy.assert_any_call(
					CopySource={
						"Bucket": "test-bucket",
						"Key": self.target.object_key(old_blob.key, is_private),
					},
					Bucket="test-bucket",
					Key=self.target.object_key(self.location(old_blob).key, is_private),
				)
			canonical_key = f"sites/{frappe.local.site}/storage/{blob.name}/report.pdf"
			self.assertEqual(self.location(blob).key, canonical_key)
			self.assertEqual(self.target.read(canonical_key).read(), b"legacy-s3")
			self.assertFalse(self.source.exists(blob.key))
			private_key = f"sites/{frappe.local.site}/storage/{private.name}/private.txt"
			self.assertEqual(self.location(private).key, private_key)
			self.assertEqual(self.target.read(private_key, is_private=True).read(), b"private-s3")
			self.assertFalse(self.source.exists(private.key, is_private=True))
			self.assertEqual(frappe.db.get_value("File", file_doc.name, "file_url"), file_doc.file_url)
			self.assertEqual(self.location(local), {"driver": "local", "key": local.key})
			self.assertEqual(local_driver.read(local.key).read(), b"keep-local")

	def test_s3_key_patch_reports_failures_and_can_be_retried(self):
		with self.set_user("testperm@example.com"):
			self.source = self.target = self.s3_driver()
			blob = self.insert_blob(b"retry-s3", key="old-site/{name}/retry.txt")
			with (
				patch.object(relocate, "get_relocation_batch", side_effect=self.scoped_batch),
				patch.object(relocate, "get_driver", side_effect=self.driver_for),
				patch.object(relocate, "_commit_batch", side_effect=frappe.db.after_commit.run),
			):
				with patch.object(
					self.source.test_client, "copy", side_effect=StubClientError("AccessDenied")
				):
					self.assertRaisesRegex(
						frappe.ValidationError, "S3 blob migration failed", migrate_s3_blob_keys.execute
					)
				self.assertEqual(self.location(blob).key, blob.key)
				self.assertTrue(self.source.exists(blob.key))
				self.source.test_client.delete_object.assert_not_called()
				migrate_s3_blob_keys.execute()
			self.assertNotEqual(self.location(blob).key, blob.key)
			self.assertEqual(self.target.read(self.location(blob).key).read(), b"retry-s3")

	def test_s3_key_patch_reuses_a_copy_after_the_row_update_fails(self):
		with self.set_user("testperm@example.com"):
			self.source = self.target = self.s3_driver()
			blob = self.insert_blob(b"reuse-copy", key="old-site/{name}/retry.txt", is_private=True)
			client = self.source.test_client
			client.upload_fileobj.reset_mock()
			with (
				patch.object(relocate, "get_relocation_batch", side_effect=self.scoped_batch),
				patch.object(relocate, "get_driver", side_effect=self.driver_for),
				patch.object(relocate, "_commit_batch", side_effect=frappe.db.after_commit.run),
			):
				with patch.object(relocate, "lock_blob", side_effect=OSError("database unavailable")):
					self.assertRaisesRegex(
						frappe.ValidationError, "S3 blob migration failed", migrate_s3_blob_keys.execute
					)
				self.assertEqual(self.location(blob).key, blob.key)
				self.assertTrue(self.source.exists(blob.key, is_private=True))
				client.delete_object.assert_not_called()
				migrate_s3_blob_keys.execute()
			self.assertEqual(client.copy.call_count, 1)
			client.get_object.assert_not_called()
			client.upload_fileobj.assert_not_called()
			self.assertEqual(self.target.read(self.location(blob).key, is_private=True).read(), b"reuse-copy")
			self.assertFalse(self.source.exists(blob.key, is_private=True))

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

	def test_renamed_site_blobs_move_to_this_sites_prefix(self):
		"""Rows under a former site name move to this site's prefix; URLs stay, and the old
		objects stay too because the driver refuses deletes outside this site's prefix."""
		s3 = self.s3_driver()
		blob = self.renamed_blob(s3)
		file_doc = self.insert_file(blob, "/files/a.txt")

		stats = self.run_renamed_relocation(s3)

		self.assertEqual((stats["moved"], stats["errors"]), (1, 0))
		self.assertEqual(self.location(blob).key, self.own_key(blob))
		self.assertEqual(s3.read(self.own_key(blob)).read(), b"renamed")
		self.assertTrue(s3.exists(blob.key))
		self.assertEqual(frappe.db.get_value("File", file_doc.name, "file_url"), "/files/a.txt")
		self.assertEqual(self.run_renamed_relocation(s3)["moved"], 0)

	def test_only_rows_under_another_site_are_relocated(self):
		"""Legacy keys keep their place: moving them deletes bytes old backups still read."""
		s3 = self.s3_driver()
		legacy = self.insert_blob(b"legacy", key="old-site/{name}/a.txt", driver=s3)

		stats = self.run_renamed_relocation(s3)

		self.assertEqual(stats["moved"], 0)
		self.assertEqual(self.location(legacy).key, legacy.key)
		s3.client.copy.assert_not_called()

	def test_renamed_relocation_is_a_no_op_without_s3(self):
		"""Sites on another driver have no site-named keys to move."""
		blob = self.insert_blob(b"local", key="sites/old.example/storage/{name}/a.txt", driver=self.target)

		stats = self.run_renamed_relocation(self.target)

		self.assertEqual(stats, {"moved": 0, "bytes": 0, "skipped": 0, "errors": 0})
		self.assertEqual(self.location(blob).key, blob.key)

	def test_a_source_outside_this_bucket_is_skipped(self):
		"""A restored source site's object may live in another bucket; relocation copies only
		inside this bucket, so the row stays and the run does not fail."""
		s3 = self.s3_driver()
		blob = self.renamed_blob(s3)
		s3.client.delete_object(Bucket=s3.bucket, Key=s3.object_key(blob.key))
		s3.client.copy.reset_mock()

		stats = self.run_renamed_relocation(s3)

		self.assertEqual((stats["moved"], stats["skipped"], stats["errors"]), (0, 1, 0))
		self.assertEqual(self.location(blob).key, blob.key)
		s3.client.copy.assert_not_called()

	def test_server_side_copies_run_in_parallel(self):
		"""Same-bucket copies run in a thread pool, capped at RELOCATE_WORKERS."""
		s3 = self.s3_driver()
		blobs = [self.renamed_blob(s3) for _ in range(relocate.RELOCATE_WORKERS + 4)]
		copy = s3.client.copy.side_effect
		active, peak, guard = [0], [0], threading.Lock()

		def slow_copy(**kwargs):
			with guard:
				active[0] += 1
				peak[0] = max(peak[0], active[0])
			time.sleep(0.05)
			copy(**kwargs)
			with guard:
				active[0] -= 1

		s3.client.copy.side_effect = slow_copy
		stats = self.run_renamed_relocation(s3)

		self.assertEqual(stats["moved"], len(blobs))
		self.assertGreater(peak[0], 1)
		self.assertLessEqual(peak[0], relocate.RELOCATE_WORKERS)

	def test_a_failed_copy_counts_an_error_and_the_rest_still_move(self):
		"""One failing copy does not stop the batch; its row keeps its source."""
		s3 = self.s3_driver()
		failing, other = self.renamed_blob(s3), self.renamed_blob(s3)
		copy = s3.client.copy.side_effect

		def copy_or_fail(CopySource, Bucket, Key):
			if failing.name in Key:
				raise StubClientError("AccessDenied")
			copy(CopySource=CopySource, Bucket=Bucket, Key=Key)

		s3.client.copy.side_effect = copy_or_fail
		stats = self.run_renamed_relocation(s3)

		self.assertEqual((stats["moved"], stats["errors"]), (1, 1))
		self.assertEqual(self.location(failing).key, failing.key)
		self.assertEqual(self.location(other).key, self.own_key(other))
