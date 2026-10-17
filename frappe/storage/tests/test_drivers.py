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
		self.key = frappe.generate_hash(length=10) + "/driver-test.txt"
		self.content = b"storage-v2-driver-test-" + frappe.generate_hash(length=20).encode()

	def test_write_read_exists_delete(self):
		self.assertFalse(self.driver.exists(self.key))
		self.assertRaises(FileNotFoundError, self.driver.read, self.key)

		# write must consume any readable, not only BytesIO
		self.driver.write(self.key, io.BufferedReader(io.BytesIO(self.content)))
		self.assertTrue(self.driver.exists(self.key))
		with self.driver.read(self.key) as stream:
			self.assertNotIsInstance(stream, bytes)
			# incremental reads work
			self.assertEqual(stream.read(4) + stream.read(), self.content)

		self.driver.delete(self.key)
		self.assertFalse(self.driver.exists(self.key))
		# deleting a missing key must not raise
		self.driver.delete(self.key)

	def test_public_and_private_namespaces_are_separate(self):
		self.driver.write(self.key, io.BytesIO(b"public bytes"))
		self.assertFalse(self.driver.exists(self.key, is_private=True))

		self.driver.write(self.key, io.BytesIO(b"private bytes"), is_private=True)
		with self.driver.read(self.key) as public, self.driver.read(self.key, is_private=True) as private:
			self.assertEqual(public.read(), b"public bytes")
			self.assertEqual(private.read(), b"private bytes")

		self.driver.delete(self.key, is_private=True)
		self.assertTrue(self.driver.exists(self.key))
		self.assertFalse(self.driver.exists(self.key, is_private=True))

	def test_read_range_returns_inclusive_slice(self):
		self.driver.write(self.key, io.BytesIO(self.content), is_private=True)
		with self.driver.read_range(self.key, 2, 8, is_private=True) as stream:
			self.assertEqual(stream.read(), self.content[2:9])
		# an open end returns the tail
		with self.driver.read_range(self.key, 7, None, is_private=True) as stream:
			self.assertEqual(stream.read(), self.content[7:])


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
		driver.get_files_dir = lambda is_private=False: os.path.join(
			tmpdir, "private" if is_private else "public", "files"
		)
		return driver

	def test_files_sit_at_their_key_and_delete_removes_the_empty_folder(self):
		self.driver.write(self.key, io.BytesIO(self.content))
		files_dir = os.path.join(self.tmpdir, "public", "files")
		path = os.path.join(files_dir, *self.key.split("/"))
		self.assertEqual(os.path.realpath(self.driver.get_path(self.key)), os.path.realpath(path))
		with open(path, "rb") as file:
			self.assertEqual(file.read(), self.content)

		self.driver.delete(self.key)

		self.assertFalse(os.path.exists(os.path.dirname(path)))
		self.assertTrue(os.path.isdir(files_dir))

	def test_keys_outside_the_files_dir_are_rejected(self):
		for key in ("../../../etc/passwd", "ab/../../../../etc/passwd", "..", "/etc/passwd"):
			for operation in (
				lambda k: self.driver.get_path(k),
				lambda k: self.driver.exists(k),
				lambda k: self.driver.read(k),
				lambda k: self.driver.delete(k),
				lambda k: self.driver.write(k, io.BytesIO(b"x")),
			):
				self.assertRaises(ValueError, operation, key)

		# a key resolving through a symlink out of the files dir
		files_dir = self.driver.get_files_dir()
		os.makedirs(files_dir, exist_ok=True)
		outside = tempfile.mkdtemp(prefix="frappe-storage-outside-")
		self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
		os.symlink(outside, os.path.join(files_dir, "link"))
		self.assertRaises(ValueError, self.driver.get_path, "link/escape")


class TestFake(IntegrationTestCase):
	def test_fake_swaps_and_restores_driver(self):
		before_override = getattr(frappe.local, "storage_driver_override", None)
		before = get_driver()

		with fake() as outer:
			self.assertIsInstance(outer, MemoryDriver)
			self.assertIs(get_driver(), outer)
			self.assertIs(frappe.storage.get_driver(), outer)
			with fake() as inner:
				self.assertIsNot(inner, outer)
				self.assertIs(get_driver(), inner)
			self.assertIs(get_driver(), outer)

		self.assertEqual(getattr(frappe.local, "storage_driver_override", None), before_override)
		self.assertIs(get_driver(), before)

		with self.assertRaises(RuntimeError), fake():
			raise RuntimeError("boom")
		self.assertIs(get_driver(), before)

	def test_fake_yields_isolated_store(self):
		with fake() as store:
			get_driver().write("ab/cd/key", io.BytesIO(b"hello"))
			self.assertTrue(store.exists("ab/cd/key"))
		with fake() as store:
			self.assertFalse(store.exists("ab/cd/key"))
