# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import io
import os
from unittest.mock import patch

import frappe
from frappe.storage.blob import put_blob
from frappe.storage.cache import (
	cache_blob,
	delete_cached,
	get_cache_path,
	get_cached_path,
	get_max_cached_file_size,
)
from frappe.storage.gc import MIN_AGE_HOURS, collect_garbage
from frappe.storage.local_driver import LocalDriver
from frappe.storage.memory_driver import MemoryDriver
from frappe.storage.serve import stream_blob
from frappe.storage.tests import storage_v2, unique_bytes, use_driver
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, set_request


def max_file_size_mb(limit_mb: int):
	return patch.dict(frappe.conf, {"storage_local_cache_config": {"max_file_size_mb": limit_mb}})


class RemoteDriver(MemoryDriver):
	"""Remote driver with a native URL and a local cache, like S3."""

	name = "remote"
	cache_locally = True

	def download_url(
		self, key, filename, expires_in, *, is_private=False, mime_type=None, as_attachment=False
	):
		return f"https://cdn.example/{key}"


class TestBlobCache(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.enterContext(
			patch.dict(
				frappe.conf,
				{"storage_local_cache": 1, "storage_local_cache_config": {"max_file_size_mb": 100}},
			)
		)
		self.blobs = []

	def tearDown(self):
		for blob in self.blobs:
			delete_cached(blob)
		super().tearDown()

	def put_blob(self, content: bytes = b"", **kwargs):
		blob = put_blob(io.BytesIO(content or unique_bytes(b"cache ")), **kwargs)
		self.blobs.append(blob)
		return blob

	def stream(self, blob, **kwargs):
		set_request(method="GET", path=f"/files/{blob.name}/a.bin")
		return stream_blob(blob, "a.bin", allow_native_redirect=True, **kwargs)

	def test_first_request_queues_a_download_and_later_ones_read_the_cache(self):
		content = unique_bytes(b"cache me ")
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.put_blob(content, filename="a.bin")

			with patch("frappe.enqueue") as enqueue:
				response = self.stream(blob)
			self.assertEqual(response.status_code, 302)
			enqueue.assert_called_once()
			self.assertEqual(enqueue.call_args.kwargs["blob_name"], blob.name)
			self.assertTrue(enqueue.call_args.kwargs["deduplicate"])
			self.assertIsNone(get_cached_path(blob))

			cache_blob(blob.name)
			with patch("frappe.enqueue") as enqueue:
				response = self.stream(blob)
			enqueue.assert_not_called()
			self.assertEqual(response.status_code, 200)
			self.assertEqual(b"".join(response.response), content)
			response.close()

	def test_cache_serves_x_accel_and_ranges(self):
		content = unique_bytes(b"range ") * 4
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.put_blob(content, filename="a.bin", is_private=True)
			cache_blob(blob.name)

			set_request(method="GET", path="/dav/a.bin", headers={"X-Use-X-Accel-Redirect": "1"})
			response = stream_blob(blob, "a.bin", allow_native_redirect=True)
			private_path = frappe.local.conf.get("private_path", "private")
			self.assertEqual(
				response.headers["X-Accel-Redirect"], f"/protected/{private_path}/files/{blob.name}/a.bin"
			)
			self.assertTrue(get_cache_path(blob).endswith(f"private/files/{blob.name}/a.bin"))

			set_request(method="GET", path="/dav/a.bin", headers={"Range": "bytes=2-6"})
			response = stream_blob(blob, "a.bin")
			self.assertEqual(response.status_code, 206)
			self.assertEqual(b"".join(response.response), content[2:7])
			response.close()

	def test_a_driver_that_does_not_cache_is_never_cached(self):
		with storage_v2(), use_driver(MemoryDriver()):
			blob = self.put_blob()
			with patch("frappe.enqueue") as enqueue:
				set_request(method="GET", path="/dav/a.bin")
				stream_blob(blob, "a.bin").close()
			enqueue.assert_not_called()
			self.assertIsNone(get_cached_path(blob))

	def test_a_download_with_the_wrong_size_leaves_no_cache_file(self):
		with storage_v2(), use_driver(RemoteDriver()) as driver:
			blob = self.put_blob()
			driver.blobs[(False, blob.key)] = b"truncated"
			with self.assertRaises(OSError):
				cache_blob(blob.name)
			self.assertFalse(os.path.exists(os.path.dirname(get_cache_path(blob))))
			self.assertIsNone(get_cached_path(blob))

	def test_a_blob_deleted_during_its_download_leaves_no_cache_file(self):
		with storage_v2(), use_driver(RemoteDriver()) as driver:
			blob = self.put_blob()
			read = driver.read

			def read_then_delete_row(key, *, is_private=False):
				frappe.db.delete("File Blob", blob.name)
				return read(key, is_private=is_private)

			with patch.object(driver, "read", read_then_delete_row):
				cache_blob(blob.name)
			self.assertFalse(os.path.exists(os.path.dirname(get_cache_path(blob))))

	def test_nothing_is_cached_unless_the_site_flag_is_on(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.put_blob(filename="a.bin")
			cache_blob(blob.name)
			self.assertIsNotNone(get_cached_path(blob))

			with patch.dict(frappe.conf, {"storage_local_cache": 0}), patch("frappe.enqueue") as enqueue:
				self.assertIsNone(get_cached_path(blob))
				self.assertEqual(self.stream(blob).status_code, 302)
			enqueue.assert_not_called()

	def test_only_blobs_within_the_size_limit_are_queued(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.put_blob(b"x" * 1024, filename="a.bin")
			cases = ((1, True), (0, False))
			for limit_mb, queued in cases:
				with self.subTest(limit_mb=limit_mb):
					with max_file_size_mb(limit_mb), patch("frappe.enqueue") as enqueue:
						self.assertEqual(self.stream(blob).status_code, 302)
					self.assertEqual(enqueue.called, queued)

			big = self.put_blob(b"x" * (2 * 1024 * 1024 + 1), filename="big.bin")
			with max_file_size_mb(2), patch("frappe.enqueue") as enqueue:
				self.stream(big)
			enqueue.assert_not_called()

	def test_settings_without_site_config_take_their_defaults(self):
		with patch.dict(frappe.conf, {"storage_local_cache_config": None}):
			self.assertEqual(get_max_cached_file_size(), 100 * 1024 * 1024)

	def test_file_blob_reports_whether_its_bytes_are_on_disk(self):
		with storage_v2():
			with use_driver(RemoteDriver()):
				remote = self.put_blob(filename="a.bin")
				self.assertFalse(remote.is_on_disk)
				cache_blob(remote.name)
				self.assertTrue(remote.is_on_disk)
				delete_cached(remote)
				self.assertFalse(remote.is_on_disk)

			with use_driver(LocalDriver()):
				self.assertTrue(self.put_blob(filename="a.bin").is_on_disk)

			with frappe.storage.fake():
				self.assertFalse(self.put_blob().is_on_disk)

	def test_the_redirect_is_cacheable_by_browsers_only_when_no_local_copy_is_coming(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.put_blob(filename="a.bin")
			cases = (
				({"storage_local_cache": 1}, 100, "no-cache"),
				({"storage_local_cache": 0}, 100, "public, max-age=1800"),
				({"storage_local_cache": 1}, 0, "public, max-age=1800"),
			)
			for conf, limit_mb, cache_control in cases:
				with self.subTest(conf=conf, limit_mb=limit_mb):
					with patch.dict(frappe.conf, conf), max_file_size_mb(limit_mb), patch("frappe.enqueue"):
						response = self.stream(blob)
					self.assertEqual(response.headers["Cache-Control"], cache_control)

	def test_a_job_for_a_deleted_blob_does_nothing(self):
		cache_blob("missing-blob")

	def test_a_public_copy_sits_at_its_url_path_for_nginx(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.put_blob(filename="a.bin")
			cache_blob(blob.name)
			path = get_cache_path(blob)
			self.assertTrue(path.endswith(f"public/files/{blob.name}/a.bin"))
			self.assertTrue(os.path.isfile(path))

	def test_garbage_collection_deletes_the_cache_file(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.put_blob()
			cache_blob(blob.name)
			frappe.db.set_value(
				"File Blob",
				blob.name,
				"modified",
				add_to_date(None, hours=-MIN_AGE_HOURS - 1),
				update_modified=False,
			)
			collect_garbage()
			self.assertFalse(os.path.exists(get_cache_path(blob)))
