# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import io
import os
import shutil
import tempfile

import frappe
import frappe.storage
from frappe.storage.driver import get_driver
from frappe.storage.local_driver import LocalDriver
from frappe.storage.memory_driver import MemoryDriver, fake
from frappe.tests import IntegrationTestCase


class DriverContractTests:
	"""Contract every StorageDriver must honor. Mixed into one TestCase per driver."""

	def make_driver(self):
		raise NotImplementedError

	def setUp(self):
		super().setUp()
		self.driver = self.make_driver()
		self.key = "ab/cd/" + frappe.generate_hash(length=40)
		self.content = b"storage-v2-driver-test-" + frappe.generate_hash(length=20).encode()

	def test_write_read_roundtrip(self):
		self.driver.write(self.key, io.BytesIO(self.content))
		stream = self.driver.read(self.key)
		try:
			self.assertEqual(stream.read(), self.content)
		finally:
			stream.close()

	def test_write_read_roundtrip_private(self):
		self.driver.write(self.key, io.BytesIO(self.content), is_private=True)
		stream = self.driver.read(self.key, is_private=True)
		try:
			self.assertEqual(stream.read(), self.content)
		finally:
			stream.close()

	def test_exists(self):
		self.assertFalse(self.driver.exists(self.key))
		self.driver.write(self.key, io.BytesIO(self.content))
		self.assertTrue(self.driver.exists(self.key))

	def test_public_and_private_namespaces_are_separate(self):
		self.driver.write(self.key, io.BytesIO(b"public bytes"))
		self.assertFalse(self.driver.exists(self.key, is_private=True))

		self.driver.write(self.key, io.BytesIO(b"private bytes"), is_private=True)
		with self.driver.read(self.key) as public, self.driver.read(self.key, is_private=True) as private:
			self.assertEqual(public.read(), b"public bytes")
			self.assertEqual(private.read(), b"private bytes")

	def test_delete(self):
		self.driver.write(self.key, io.BytesIO(self.content))
		self.driver.delete(self.key)
		self.assertFalse(self.driver.exists(self.key))
		# deleting a missing key must not raise
		self.driver.delete(self.key)

	def test_delete_only_touches_one_namespace(self):
		self.driver.write(self.key, io.BytesIO(self.content))
		self.driver.write(self.key, io.BytesIO(self.content), is_private=True)
		self.driver.delete(self.key, is_private=True)
		self.assertTrue(self.driver.exists(self.key))
		self.assertFalse(self.driver.exists(self.key, is_private=True))

	def test_read_missing_key_raises(self):
		self.assertRaises(FileNotFoundError, self.driver.read, self.key)

	def test_read_returns_stream(self):
		self.driver.write(self.key, io.BytesIO(self.content))
		stream = self.driver.read(self.key)
		try:
			self.assertNotIsInstance(stream, bytes)
			self.assertTrue(callable(stream.read))
			# incremental reads work
			head = stream.read(4)
			rest = stream.read()
			self.assertEqual(head + rest, self.content)
		finally:
			stream.close()

	def test_streamed_write(self):
		# write must consume any readable, not only BytesIO
		chunks = [b"chunk-one:", b"chunk-two:", b"chunk-three"]
		self.driver.write(self.key, io.BufferedReader(io.BytesIO(b"".join(chunks))))
		with self.driver.read(self.key) as stream:
			self.assertEqual(stream.read(), b"".join(chunks))


class TestMemoryDriverContract(DriverContractTests, IntegrationTestCase):
	def make_driver(self):
		return MemoryDriver()


class TestLocalDriverContract(DriverContractTests, IntegrationTestCase):
	def make_driver(self):
		tmpdir = tempfile.mkdtemp(prefix="frappe-storage-test-")
		self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
		self.tmpdir = tmpdir

		driver = LocalDriver()
		# keep tests off the real site's files; path-safety logic is unchanged
		driver.get_blobs_dir = lambda is_private=False: os.path.join(
			tmpdir, "private" if is_private else "public", "files", "blobs"
		)
		return driver

	def test_writes_stay_inside_tempdir(self):
		self.driver.write(self.key, io.BytesIO(self.content))
		path = self.driver.get_path(self.key)
		self.assertTrue(path.startswith(os.path.realpath(self.tmpdir)))
		self.assertTrue(os.path.isfile(path))

	def test_path_traversal_keys_rejected(self):
		bad_keys = (
			"../../../etc/passwd",
			"ab/../../../../etc/passwd",
			"..",
			"/etc/passwd",
		)
		for key in bad_keys:
			for operation in (
				lambda k: self.driver.get_path(k),
				lambda k: self.driver.exists(k),
				lambda k: self.driver.read(k),
				lambda k: self.driver.delete(k),
				lambda k: self.driver.write(k, io.BytesIO(b"x")),
			):
				self.assertRaises(ValueError, operation, key)

	def test_symlink_escape_rejected(self):
		# a key resolving through a symlink out of the blobs dir must be rejected
		blobs_dir = self.driver.get_blobs_dir()
		os.makedirs(blobs_dir, exist_ok=True)
		outside = tempfile.mkdtemp(prefix="frappe-storage-outside-")
		self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
		os.symlink(outside, os.path.join(blobs_dir, "link"))
		self.assertRaises(ValueError, self.driver.get_path, "link/escape")


class TestFake(IntegrationTestCase):
	def test_fake_swaps_and_restores_driver(self):
		before_override = getattr(frappe.local, "storage_driver_override", None)
		before = get_driver()

		with fake() as store:
			self.assertIsInstance(store, MemoryDriver)
			self.assertIs(get_driver(), store)
			self.assertIs(frappe.storage.get_driver(), store)

		self.assertEqual(getattr(frappe.local, "storage_driver_override", None), before_override)
		self.assertIs(get_driver(), before)

	def test_fake_restores_on_exception(self):
		before = get_driver()
		with self.assertRaises(RuntimeError), fake():
			raise RuntimeError("boom")
		self.assertIs(get_driver(), before)

	def test_nested_fakes_restore_in_order(self):
		with fake() as outer:
			with fake() as inner:
				self.assertIsNot(inner, outer)
				self.assertIs(get_driver(), inner)
			self.assertIs(get_driver(), outer)

	def test_fake_yields_isolated_store(self):
		with fake() as store:
			get_driver().write("ab/cd/key", io.BytesIO(b"hello"))
			self.assertTrue(store.exists("ab/cd/key"))
		with fake() as store:
			self.assertFalse(store.exists("ab/cd/key"))
