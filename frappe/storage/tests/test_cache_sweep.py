# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import contextlib
import io
import os
import time
from unittest.mock import patch

import frappe
from frappe.storage.blob import put_blob
from frappe.storage.cache import (
	cache_blob,
	cache_lock,
	delete_cached,
	get_cache_path,
	get_holding_path,
	restore_cached,
	sweep_cache,
	sweep_lock,
)
from frappe.storage.local_driver import LocalDriver
from frappe.storage.relocate import relocate_blobs
from frappe.storage.serve import stream_blob
from frappe.storage.tests import hook_value, storage_v2, unique_bytes, use_driver
from frappe.storage.tests.test_cache import RemoteDriver
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.utils.file_lock import LockTimeoutError

MINUTE = 60


def age(path: str, minutes: int) -> None:
	then = time.time() - minutes * MINUTE
	os.utime(path, (then, then))


class TestCacheSweep(IntegrationTestCase):
	"""The sweep holds old cached copies, deletes held ones, and a request restores a held copy."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.enterContext(patch.dict(frappe.conf, {"storage_local_cache": 1}))
		self.enterContext(
			hook_value("storage_drivers", {"remote": "frappe.storage.tests.test_cache.RemoteDriver"})
		)
		for fieldname, value in (
			("max_cached_file_size", 100),
			("cache_keep_minutes", 300),
			("cache_grace_minutes", 60),
		):
			frappe.db.set_single_value("System Settings", fieldname, value)
		self.blobs = []

	def tearDown(self):
		for blob in self.blobs:
			delete_cached(blob)
		frappe.db.rollback()
		super().tearDown()

	def cached_blob(self, minutes_old: int, **kwargs):
		blob = put_blob(io.BytesIO(unique_bytes(b"sweep ")), filename="a.bin", **kwargs)
		self.blobs.append(blob)
		cache_blob(blob.name)
		age(get_cache_path(blob), minutes_old)
		return blob

	def stream(self, blob):
		set_request(method="GET", path=f"/files/{blob.name}/a.bin")
		return stream_blob(blob, "a.bin", allow_native_redirect=True)

	def test_sweep_holds_only_copies_older_than_the_keep_time(self):
		with storage_v2(), use_driver(RemoteDriver()):
			old = self.cached_blob(301)
			fresh = self.cached_blob(299, is_private=True)
			sweep_cache()

			self.assertFalse(os.path.exists(get_cache_path(old)))
			self.assertTrue(os.path.isfile(get_holding_path(old)))
			self.assertTrue(os.path.isfile(get_cache_path(fresh)))
			self.assertFalse(os.path.exists(get_holding_path(fresh)))

	def test_sweep_leaves_files_that_are_not_cached_copies(self):
		flat_file = frappe.utils.get_files_path("sweep-test-v1.txt")
		with storage_v2(), use_driver(LocalDriver()):
			local = put_blob(io.BytesIO(unique_bytes(b"local ")), filename="a.bin")
			self.blobs.append(local)
			with open(flat_file, "w") as file:
				file.write("v1")
			try:
				age(get_cache_path(local), 1000)
				age(flat_file, 1000)
				sweep_cache()
				self.assertTrue(os.path.isfile(get_cache_path(local)))
				self.assertTrue(os.path.isfile(flat_file))
			finally:
				os.remove(flat_file)

	def test_a_request_restores_a_held_copy_and_restarts_its_clock(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.cached_blob(301)
			sweep_cache()

			with patch("frappe.enqueue") as enqueue:
				response = self.stream(blob)
			self.assertEqual(response.status_code, 200)
			response.close()
			enqueue.assert_not_called()
			self.assertTrue(os.path.isfile(get_cache_path(blob)))
			self.assertFalse(os.path.exists(get_holding_path(blob)))
			self.assertLess(time.time() - os.path.getmtime(get_cache_path(blob)), MINUTE)

			sweep_cache()
			self.assertTrue(os.path.isfile(get_cache_path(blob)))

	def test_sweep_deletes_held_copies_older_than_the_grace_time(self):
		with storage_v2(), use_driver(RemoteDriver()):
			expired = self.cached_blob(301)
			waiting = self.cached_blob(301)
			sweep_cache()
			age(get_holding_path(expired), 61)
			age(get_holding_path(waiting), 59)
			sweep_cache()

			self.assertFalse(os.path.exists(get_holding_path(expired)))
			self.assertTrue(os.path.isfile(get_holding_path(waiting)))

			with patch("frappe.enqueue") as enqueue:
				self.assertEqual(self.stream(expired).status_code, 302)
			enqueue.assert_called_once()

	def test_with_the_flag_off_nothing_is_restored_and_copies_still_age_out(self):
		with storage_v2(), use_driver(RemoteDriver()):
			held = self.cached_blob(301)
			sweep_cache()
			stale = self.cached_blob(301)

			with patch.dict(frappe.conf, {"storage_local_cache": 0}):
				self.assertEqual(self.stream(held).status_code, 302)
				self.assertTrue(os.path.isfile(get_holding_path(held)))
				sweep_cache()
			self.assertTrue(os.path.isfile(get_holding_path(stale)))

	def test_a_locked_blob_is_skipped_not_waited_for(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.cached_blob(301)
			with cache_lock(blob.name, 1), patch("frappe.storage.cache.SWEEP_LOCK_TIMEOUT", 0.1):
				self.assertEqual(sweep_cache()["held"], 0)
			self.assertTrue(os.path.isfile(get_cache_path(blob)))

			sweep_cache()
			with cache_lock(blob.name, 1), patch("frappe.storage.cache.RESTORE_LOCK_TIMEOUT", 0.1):
				self.assertIsNone(restore_cached(blob))
			self.assertTrue(os.path.isfile(get_holding_path(blob)))

	def test_the_sweep_and_a_relocation_never_run_together(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.cached_blob(301)
			with sweep_lock(1):
				with patch("frappe.storage.cache.SWEEP_LOCK_TIMEOUT", 0.1):
					self.assertEqual(sweep_cache()["held"], 0)
				with (
					patch("frappe.storage.relocate.SWEEP_WAIT_TIMEOUT", 0.1),
					self.assertRaises(LockTimeoutError),
				):
					relocate_blobs()
			self.assertTrue(os.path.isfile(get_cache_path(blob)))

	def test_a_copy_restored_right_after_the_sweep_holds_it_stays(self):
		with storage_v2(), use_driver(RemoteDriver()):
			blob = self.cached_blob(301)
			restored = []

			@contextlib.contextmanager
			def lock_then_restore(blob_name, timeout):
				with cache_lock(blob_name, timeout):
					yield
				if not restored:
					restored.append(blob_name)
					restore_cached(blob)

			with patch("frappe.storage.cache.cache_lock", lock_then_restore):
				sweep_cache()
			self.assertTrue(restored)
			self.assertTrue(os.path.isfile(get_cache_path(blob)))
			self.assertFalse(os.path.exists(os.path.dirname(get_holding_path(blob))))
