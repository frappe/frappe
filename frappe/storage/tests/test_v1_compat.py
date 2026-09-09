# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""FileV1 with the ``storage_v2`` flag off.

Two groups:

- The compat shim. Turning the flag off is the documented rollback
  lever, so a site can hold blob-backed rows while FileV1 is the
  controller. Those rows must be handed back to FileV2.
- The legacy disk paths that only FileV1 has: the ``write_file`` and
  ``delete_file_data_content`` hooks, and the rollback of an in-place
  content write or a privacy move.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.core.doctype.file import file_v1
from frappe.core.doctype.file.file_v1 import FileV1
from frappe.storage import fake
from frappe.storage.tests import reset_file_controller
from frappe.tests import IntegrationTestCase
from frappe.utils import get_files_path, get_url

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
def flag_off():
	"""Disable storage_v2 in site conf for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf["storage_v2"] = 0
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
def hook_methods(**methods):
	"""Patch the ``get_hook_method`` FileV1 uses, for the duration of the block.

	``get_hook_method`` reads the whole hooks dict, so ``patch_hooks``,
	which matches on the hook name, never reaches it."""

	def get_hook_method(hook_name, fallback=None):
		return methods.get(hook_name, fallback)

	with patch.object(file_v1, "get_hook_method", get_hook_method):
		yield


def unique_png():
	return PNG_MAGIC + frappe.generate_hash(length=32).encode()


def unique_text(prefix=b"v1-compat-"):
	return prefix + frappe.generate_hash(length=32).encode() + b"\n"


class V1CompatTestCase(IntegrationTestCase):
	def delete_later(self, doctype, name):
		self.addCleanup(
			frappe.delete_doc, doctype, name, force=1, ignore_permissions=True, ignore_missing=True
		)

	def remove_later(self, path):
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

	def blob_backed_file(self, content=None, label="blob", is_private=1):
		"""Insert a blob-backed File row with the flag ON.

		The rollback fixture: a row created while storage_v2 was on, then
		used after the flag goes off."""
		with flag_on():
			file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"{label}-{frappe.generate_hash(length=10)}.png",
					"content": unique_png() if content is None else content,
					"is_private": is_private,
				}
			).insert()
		self.delete_later("File", file.name)
		self.delete_later("File Blob", file.blob)
		return file

	def legacy_file(self, content=None, label="legacy", is_private=0, extension="txt"):
		"""Insert a plain disk-backed File row. Call inside ``flag_off()``."""
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{label}-{frappe.generate_hash(length=10)}.{extension}",
				"content": unique_text() if content is None else content,
				"is_private": is_private,
			}
		).insert()
		self.delete_later("File", file.name)
		return file


class TestV1BlobCompatShim(V1CompatTestCase):
	"""Blob-backed rows read and written through FileV1."""

	def test_insert_from_f_url_relinks_blob(self):
		# an amend or attachment copy carries only the /f/ file_url; FileV1
		# must relink the blob instead of failing URL validation
		with fake():
			original = self.blob_backed_file(label="relink")

			with flag_off():
				copy = frappe.get_doc(
					{
						"doctype": "File",
						"file_url": original.file_url,
						"file_name": original.file_name,
						"is_private": 1,
					}
				).insert()
				self.delete_later("File", copy.name)

				self.assertEqual(copy.blob, original.blob)
				self.assertEqual(copy.file_url, original.file_url)
				self.assertTrue(copy.exists_on_disk())

	def test_insert_from_existing_blob_flag_sets_url(self):
		from frappe.core.doctype.file.file_v2 import create_file_from_blob

		with fake():
			original = self.blob_backed_file(label="from-blob")
			blob = frappe.get_doc("File Blob", original.blob)

			with flag_off():
				file = create_file_from_blob(blob, "handed-over.png", is_private=True)
				self.delete_later("File", file.name)

				self.assertEqual(file.blob, blob.name)
				self.assertEqual(file.file_url, f"/f/{blob.name}/handed-over.png")

	def test_get_content_reads_through_driver(self):
		content = unique_png()
		with fake():
			file = self.blob_backed_file(content, label="read")

			with flag_off():
				fresh = frappe.get_doc("File", file.name)
				self.assertEqual(fresh.get_content(), content)

	def test_get_full_path_and_exists_on_disk_use_the_blob_key(self):
		import frappe.storage

		content = unique_png()
		# no fake(): the local driver puts real bytes on disk, so there is a path
		file = self.blob_backed_file(content, label="fullpath")
		blob = frappe.get_doc("File Blob", file.blob)
		driver = frappe.storage.get_driver("local")
		self.addCleanup(driver.delete, blob.key, is_private=True)

		with flag_off():
			fresh = frappe.get_doc("File", file.name)
			path = fresh.get_full_path()
			self.assertTrue(os.path.isfile(path))
			with open(path, "rb") as f:
				self.assertEqual(f.read(), content)
			self.assertTrue(fresh.exists_on_disk())

	def test_validate_file_on_disk_throws_for_missing_bytes(self):
		with fake() as store:
			file = self.blob_backed_file(label="missing")
			blob = frappe.get_doc("File Blob", file.blob)
			store.delete(blob.key, is_private=True)

			with flag_off():
				fresh = frappe.get_doc("File", file.name)
				self.assertFalse(fresh.exists_on_disk())
				self.assertRaises(OSError, fresh.validate_file_on_disk)

	def test_privacy_flip_repoints_the_blob(self):
		content = unique_png()
		with fake() as store:
			file = self.blob_backed_file(content, label="flip", is_private=0)
			old_blob = file.blob

			with flag_off():
				fresh = frappe.get_doc("File", file.name)
				fresh.is_private = 1
				fresh.handle_is_private_changed()
				self.delete_later("File Blob", fresh.blob)

				self.assertNotEqual(fresh.blob, old_blob)
				new_blob = frappe.get_doc("File Blob", fresh.blob)
				self.assertEqual(new_blob.is_private, 1)
				self.assertEqual(fresh.file_url, f"/f/{new_blob.name}/{fresh.file_name}")
				self.assertTrue(store.exists(new_blob.key, is_private=True))
				# blobs are immutable; the old one is left for garbage collection
				self.assertTrue(frappe.db.exists("File Blob", old_blob))

	def test_before_save_reasserts_blob_privacy(self):
		# a File subclass may override validate() without calling super(),
		# so handle_is_private_changed never runs; before_save is the backstop
		with fake() as store:
			file = self.blob_backed_file(label="backstop", is_private=0)
			old_blob = file.blob
			frappe.db.set_value("File", file.name, "is_private", 1, update_modified=False)

			with flag_off():
				fresh = frappe.get_doc("File", file.name)
				fresh.save()
				self.delete_later("File Blob", fresh.blob)

				self.assertNotEqual(fresh.blob, old_blob)
				new_blob = frappe.get_doc("File Blob", fresh.blob)
				self.assertEqual(new_blob.is_private, 1)
				self.assertTrue(store.exists(new_blob.key, is_private=True))

	def test_delete_keeps_the_bytes(self):
		with fake() as store:
			file = self.blob_backed_file(label="keep")
			blob = frappe.get_doc("File Blob", file.blob)

			with flag_off():
				frappe.get_doc("File", file.name).delete()

			self.assertTrue(frappe.db.exists("File Blob", blob.name))
			self.assertTrue(store.exists(blob.key, is_private=True))


class TestV1LegacyDiskPaths(V1CompatTestCase):
	"""Disk-only behaviour that FileV1 keeps."""

	def test_write_file_hook_replaces_the_disk_write(self):
		calls = []

		def write_file(doc):
			calls.append(doc.file_name)
			return doc.save_file_on_filesystem()

		with flag_off(), hook_methods(write_file=write_file):
			file = self.legacy_file(label="write-hook")

		self.assertEqual(calls, [file.file_name])
		self.assertEqual(file.file_url, f"/files/{file.file_name}")
		self.assertTrue(os.path.isfile(get_files_path(file.file_name)))

	def test_delete_file_data_content_hook_replaces_the_unlink(self):
		calls = []

		def delete_file_data_content(doc, only_thumbnail=False):
			calls.append(only_thumbnail)
			doc.delete_file_from_filesystem(only_thumbnail=only_thumbnail)

		with flag_off():
			file = self.legacy_file(label="delete-hook")
			path = file.get_full_path()
			self.assertTrue(os.path.isfile(path))

			with hook_methods(delete_file_data_content=delete_file_data_content):
				file.delete()

		self.assertEqual(calls, [False])
		self.assertFalse(os.path.exists(path))

	def test_write_file_skips_a_remote_file(self):
		with flag_off():
			doc = frappe.new_doc("File")
			doc.file_name = "remote.png"
			doc.file_url = "https://example.com/remote.png"

			self.assertTrue(doc.is_remote_file)
			self.assertIsNone(doc.write_file())

	def test_validate_file_url_rejects_a_non_files_path(self):
		with flag_off():
			doc = frappe.new_doc("File")
			doc.file_name = "stray.txt"
			doc.file_url = "/somewhere-else/stray.txt"

			self.assertRaises(frappe.ValidationError, doc.validate_file_url)

	def test_get_full_path_strips_the_site_url(self):
		file_name = f"absolute-{frappe.generate_hash(length=10)}.txt"
		with flag_off():
			doc = frappe.new_doc("File")
			doc.file_name = file_name
			doc.file_url = f"{get_url()}/files/{file_name}"

			self.assertEqual(doc.get_full_path(), get_files_path(file_name))

	def test_generate_content_hash_reads_the_file(self):
		from frappe.core.doctype.file.utils import get_content_hash

		content = unique_text(b"hash-me-")
		with flag_off():
			file = self.legacy_file(content, label="hash")

			fresh = frappe.get_doc("File", file.name)
			fresh.content_hash = None
			# name is set, so the duplicate lookup excludes this row
			fresh.validate_duplicate_entry()

			self.assertEqual(fresh.content_hash, get_content_hash(content))

	def test_generate_content_hash_throws_for_a_missing_file(self):
		with flag_off():
			doc = frappe.new_doc("File")
			doc.file_name = "gone.txt"
			doc.file_url = f"/files/gone-{frappe.generate_hash(length=10)}.txt"

			self.assertRaises(frappe.ValidationError, doc.generate_content_hash)


class TestV1PrivacyChange(V1CompatTestCase):
	"""``handle_is_private_changed`` on disk-backed rows.

	Called directly, not through ``save()``: a File subclass may override
	``validate()`` without calling super(), and then ``save()`` never
	reaches this seam."""

	def test_remote_file_is_left_alone(self):
		url = f"https://example.com/{frappe.generate_hash(length=10)}.png"
		with flag_off():
			doc = frappe.new_doc("File")
			doc.file_name = "remote.png"
			doc.file_url = url
			doc.is_private = 1

			self.assertIsNone(doc.handle_is_private_changed())
			self.assertEqual(doc.file_url, url)

	def test_matching_url_is_a_noop(self):
		with flag_off():
			file = self.legacy_file(label="noop", is_private=1)
			path = file.get_full_path()

			# a doc rebuilt from a dict lands here without a real privacy
			# change: the recomputed URL equals the old one, so nothing moves
			fresh = frappe.get_doc("File", file.name)
			self.assertIsNone(fresh.handle_is_private_changed())

			self.assertEqual(fresh.file_url, file.file_url)
			self.assertTrue(os.path.isfile(path))

	def test_throws_when_the_source_file_is_gone(self):
		with flag_off():
			file = self.legacy_file(label="vanished", is_private=1)
			os.remove(file.get_full_path())

			fresh = frappe.get_doc("File", file.name)
			fresh.is_private = 0

			self.assertRaises(FileNotFoundError, fresh.handle_is_private_changed)


class TestV1Rollback(V1CompatTestCase):
	"""``on_rollback`` undoes the in-place writes only FileV1 makes.

	Called as ``FileV1.on_rollback(doc)``: a File subclass may override
	``on_rollback`` without calling super()."""

	def test_restores_the_original_text_content(self):
		original = unique_text(b"original-")
		replacement = unique_text(b"replacement-")

		with flag_off():
			file = self.legacy_file(original, label="rollback-content")
			path = file.get_full_path()

			# a fresh instance has no new_file flag, so the write is an update
			fresh = frappe.get_doc("File", file.name)
			fresh.save_file(content=replacement, overwrite=True)

			with open(path, "rb") as f:
				self.assertEqual(f.read(), replacement)
			# a text file decodes on read, so the stash is a str
			self.assertIsInstance(fresh.flags.original_content, str)

			FileV1.on_rollback(fresh)

			with open(path, "rb") as f:
				self.assertEqual(f.read(), original)
			self.assertIsNone(fresh.flags.get("original_content"))

	def test_moves_the_file_back_to_its_original_path(self):
		content = unique_text(b"moved-")
		with flag_off():
			file = self.legacy_file(content, label="rollback-path", is_private=0)
			public_path = get_files_path(file.file_name)
			private_path = get_files_path(file.file_name, is_private=1)
			self.remove_later(public_path)
			self.remove_later(private_path)

			fresh = frappe.get_doc("File", file.name)
			fresh.is_private = 1
			fresh.handle_is_private_changed()

			self.assertTrue(os.path.isfile(private_path))
			self.assertFalse(os.path.exists(public_path))
			self.assertEqual(fresh.flags.original_path["old"], Path(public_path))

			FileV1.on_rollback(fresh)

			self.assertTrue(os.path.isfile(public_path))
			self.assertFalse(os.path.exists(private_path))
			self.assertIsNone(fresh.flags.get("original_path"))
