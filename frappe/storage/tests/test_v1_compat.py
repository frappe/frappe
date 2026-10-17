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
from frappe.core.doctype.file.utils import get_content_hash
from frappe.storage import backfill, fake, get_driver
from frappe.storage.gc import MIN_AGE_HOURS, collect_garbage
from frappe.storage.tests import storage_v2, unique_bytes, unique_png
from frappe.storage.tests.test_gc_backfill import backdate
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_files_path, get_url, now_datetime


@contextmanager
def hook_methods(**methods):
	"""Patch the ``get_hook_method`` FileV1 uses, for the duration of the block.

	``get_hook_method`` reads the whole hooks dict, so ``hook_value``,
	which matches on the hook name, never reaches it."""

	def get_hook_method(hook_name, fallback=None):
		return methods.get(hook_name, fallback)

	with patch.object(file_v1, "get_hook_method", get_hook_method):
		yield


def unique_text(prefix=b"v1-compat-"):
	return unique_bytes(prefix) + b"\n"


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
		with storage_v2():
			file = frappe.get_doc(
				doctype="File",
				file_name=f"{label}-{frappe.generate_hash(length=10)}.png",
				content=unique_png() if content is None else content,
				is_private=is_private,
			).insert()
		self.delete_later("File", file.name)
		self.delete_later("File Blob", file.blob)
		return file

	def legacy_file(self, content=None, label="legacy", is_private=0):
		"""Insert a plain disk-backed File row. Call inside ``storage_v2(False)``."""
		file = frappe.get_doc(
			doctype="File",
			file_name=f"{label}-{frappe.generate_hash(length=10)}.txt",
			content=unique_text() if content is None else content,
			is_private=is_private,
		).insert()
		self.delete_later("File", file.name)
		return file


class TestV1BlobCompatShim(V1CompatTestCase):
	"""Blob-backed rows read and written through FileV1."""

	def test_new_rows_link_an_existing_blob(self):
		with fake():
			original = self.blob_backed_file(label="relink")

			with storage_v2(False):
				# an amend or attachment copy carries only the blob file_url
				copy = frappe.get_doc(
					doctype="File", file_url=original.file_url, file_name=original.file_name, is_private=1
				).insert()
				self.delete_later("File", copy.name)
				self.assertEqual((copy.blob, copy.file_url), (original.blob, original.file_url))
				self.assertTrue(copy.exists_on_disk())

	def test_reads_go_through_the_blob(self):
		content = unique_png()
		# the local driver puts real bytes on disk, so there is a path
		file = self.blob_backed_file(content, label="fullpath")
		key = frappe.db.get_value("File Blob", file.blob, "key")
		self.addCleanup(get_driver("local").delete, key, is_private=True)
		with storage_v2(False):
			fresh = frappe.get_doc("File", file.name)
			path = fresh.get_full_path()
			with open(path, "rb") as f:
				self.assertEqual(f.read(), content)
			self.assertTrue(fresh.exists_on_disk())

		with fake() as store:
			content = unique_png()
			file = self.blob_backed_file(content, label="read")
			with storage_v2(False):
				fresh = frappe.get_doc("File", file.name)
				self.assertEqual(fresh.get_content(), content)

				store.delete(frappe.db.get_value("File Blob", file.blob, "key"), is_private=True)
				self.assertFalse(fresh.exists_on_disk())
				self.assertRaises(OSError, fresh.validate_file_on_disk)

	def test_privacy_change_repoints_the_blob(self):
		with fake() as store:
			for case in ("flip", "drift"):
				with self.subTest(case=case):
					file = self.blob_backed_file(label=case, is_private=0)
					if case == "drift":
						# a File subclass may override validate() without calling super(),
						# so handle_is_private_changed never runs; before_save is the backstop
						frappe.db.set_value("File", file.name, "is_private", 1, update_modified=False)

					with storage_v2(False):
						fresh = frappe.get_doc("File", file.name)
						if case == "flip":
							fresh.is_private = 1
						fresh.save()
						self.delete_later("File Blob", fresh.blob)

					self.assertNotEqual(fresh.blob, file.blob)
					new_blob = frappe.get_doc("File Blob", fresh.blob)
					self.assertEqual(new_blob.is_private, 1)
					self.assertEqual(fresh.file_url, f"/private/files/{new_blob.name}/{fresh.file_name}")
					self.assertTrue(store.exists(new_blob.key, is_private=True))
					# blobs are immutable; the old one is left for garbage collection
					self.assertTrue(frappe.db.exists("File Blob", file.blob))

	def test_content_update_writes_a_new_blob(self):
		# optimize_file and other in-place updates must not rewrite a shared blob
		content = unique_png()
		with fake() as store:
			file = self.blob_backed_file(content, label="update")
			sibling = self.blob_backed_file(content, label="sibling")
			self.assertEqual(sibling.blob, file.blob)

			with storage_v2(False):
				fresh = frappe.get_doc("File", file.name)
				new_content = unique_png()
				fresh.save_file(content=new_content, overwrite=True)
				self.delete_later("File Blob", fresh.blob)

			def stored(blob_name):
				blob = frappe.get_doc("File Blob", blob_name)
				with store.read(blob.key, is_private=bool(blob.is_private)) as stream:
					return stream.read()

			self.assertNotEqual(fresh.blob, file.blob)
			self.assertTrue(fresh.file_url.startswith(f"/private/files/{fresh.blob}/"))
			self.assertEqual(stored(fresh.blob), new_content)
			self.assertEqual(stored(sibling.blob), content)

	def test_duplicate_upload_links_the_blob_and_keeps_it_alive(self):
		# identical bytes uploaded with the flag off must keep the blob
		# referenced, or garbage collection deletes them with the first row
		content = unique_png()
		cutoff = add_to_date(now_datetime(), hours=-MIN_AGE_HOURS)
		with fake() as store:
			first = self.blob_backed_file(content, label="dedup-first")
			blob = frappe.get_doc("File Blob", first.blob)
			backdate(blob.name)

			with storage_v2(False):
				second = frappe.get_doc(
					{"doctype": "File", "file_name": "dedup-second.png", "content": content, "is_private": 1}
				).insert()
				self.delete_later("File", second.name)
				self.assertEqual(second.blob, blob.name)
				# until the new row commits, only a fresh modified keeps a concurrent
				# GC pass from deleting the blob if the first row is deleted meanwhile
				self.assertGreater(frappe.db.get_value("File Blob", blob.name, "modified"), cutoff)

				# a File delete never removes the bytes
				first.delete()
				self.assertTrue(frappe.db.exists("File Blob", blob.name))
				self.assertTrue(store.exists(blob.key, is_private=True))

			backdate(blob.name)
			collect_garbage()
			self.assertEqual(frappe.get_doc("File", second.name).get_content(), content)

	def test_dedup_onto_a_vanished_blob_stores_its_own_bytes(self):
		# GC deleted the blob between the duplicate lookup and the link
		content = unique_png()
		with fake():
			first = self.blob_backed_file(content, label="vanished-first")

			with storage_v2(False), patch("frappe.storage.blob.revive_blob", return_value=False):
				second = frappe.get_doc(
					doctype="File", file_name="vanished-second.png", content=content, is_private=1
				).insert()
				self.delete_later("File", second.name)

			self.assertFalse(second.blob)
			self.assertNotEqual(second.file_url, first.file_url)
			self.assertTrue(second.file_url.startswith("/private/files/vanished-second"))
			self.assertEqual(frappe.get_doc("File", second.name).get_content(), content)


class TestV1LegacyDiskPaths(V1CompatTestCase):
	"""Disk-only behaviour that FileV1 keeps."""

	def test_hooks_replace_the_disk_write_and_unlink(self):
		writes, deletes = [], []

		def write_file(doc):
			writes.append(doc.file_name)
			return doc.save_file_on_filesystem()

		def delete_file_data_content(doc, only_thumbnail=False):
			deletes.append(only_thumbnail)
			doc.delete_file_from_filesystem(only_thumbnail=only_thumbnail)

		with storage_v2(False):
			with hook_methods(write_file=write_file):
				file = self.legacy_file(label="hooks")
			path = get_files_path(file.file_name)
			self.assertEqual(writes, [file.file_name])
			self.assertEqual(file.file_url, f"/files/{file.file_name}")
			self.assertTrue(os.path.isfile(path))

			with hook_methods(delete_file_data_content=delete_file_data_content):
				file.delete()
			self.assertEqual(deletes, [False])
			self.assertFalse(os.path.exists(path))

	def test_unsaved_row_paths(self):
		file_name = f"absolute-{frappe.generate_hash(length=10)}.txt"
		with storage_v2(False):
			remote = frappe.new_doc("File", file_name="remote.png", file_url="https://example.com/remote.png")
			self.assertTrue(remote.is_remote_file)
			self.assertIsNone(remote.write_file())

			stray = frappe.new_doc("File", file_name="stray.txt", file_url="/somewhere-else/stray.txt")
			self.assertRaises(frappe.ValidationError, stray.validate_file_url)

			absolute = frappe.new_doc("File", file_name=file_name, file_url=f"{get_url()}/files/{file_name}")
			self.assertEqual(absolute.get_full_path(), get_files_path(file_name))

	def test_content_hash_reads_the_file(self):
		content = unique_text(b"hash-me-")
		with storage_v2(False):
			file = self.legacy_file(content, label="hash")
			fresh = frappe.get_doc("File", file.name)
			fresh.content_hash = None
			# name is set, so the duplicate lookup excludes this row
			fresh.validate_duplicate_entry()
			self.assertEqual(fresh.content_hash, get_content_hash(content))

			gone = frappe.new_doc(
				"File", file_name="gone.txt", file_url=f"/files/gone-{frappe.generate_hash(length=10)}.txt"
			)
			self.assertRaises(frappe.ValidationError, gone.generate_content_hash)

	def test_deleting_unbackfilled_rows_under_v2(self):
		with storage_v2(False):
			lone = self.legacy_file(label="delete-unbackfilled")
			lone_path = lone.get_full_path()
			first = self.legacy_file(label="delete-shared")
			path = first.get_full_path()
			copies = [
				frappe.get_doc({"doctype": "File", "file_url": first.file_url}).insert() for _ in range(2)
			]
		self.remove_later(lone_path)
		self.remove_later(path)
		for copy in copies:
			self.delete_later("File", copy.name)

		with storage_v2():
			# no blob owns the bytes, so they go with the row
			frappe.get_doc("File", lone.name).delete()
			self.assertFalse(os.path.exists(lone_path))

			backfill.run(filters=[["name", "=", first.name]])
			blob = frappe.db.get_value("File", first.name, "blob")
			self.delete_later("File Blob", blob)
			frappe.get_doc("File", copies[0].name).delete()
			self.assertTrue(os.path.isfile(path))

			# a new upload of the same bytes reuses the blob under its own URL
			upload = frappe.get_doc(
				{"doctype": "File", "file_name": "reused.txt", "content": first.get_content()}
			).insert()
			self.delete_later("File", upload.name)
			self.assertEqual(upload.blob, blob)
			self.assertNotEqual(upload.file_url, first.file_url)

			# the last unbackfilled row keeps bytes its blob still serves
			frappe.get_doc("File", first.name).delete()
			frappe.get_doc("File", copies[1].name).delete()
			self.assertTrue(os.path.isfile(path))


class TestV1PrivacyChange(V1CompatTestCase):
	"""``handle_is_private_changed`` and ``on_rollback`` on disk-backed rows.

	Called directly, not through ``save()``: a File subclass may override
	``validate()`` or ``on_rollback`` without calling super()."""

	def test_handle_is_private_changed(self):
		url = f"https://example.com/{frappe.generate_hash(length=10)}.png"
		with storage_v2(False):
			remote = frappe.new_doc("File", file_name="remote.png", file_url=url, is_private=1)
			self.assertIsNone(remote.handle_is_private_changed())
			self.assertEqual(remote.file_url, url)

			file = self.legacy_file(label="noop", is_private=1)
			path = file.get_full_path()
			# a doc rebuilt from a dict lands here without a real privacy
			# change: the recomputed URL equals the old one, so nothing moves
			fresh = frappe.get_doc("File", file.name)
			self.assertIsNone(fresh.handle_is_private_changed())
			self.assertEqual(fresh.file_url, file.file_url)
			self.assertTrue(os.path.isfile(path))

			os.remove(path)
			fresh.is_private = 0
			self.assertRaises(FileNotFoundError, fresh.handle_is_private_changed)

	def test_rollback_restores_the_original_content(self):
		original = unique_text(b"original-")
		replacement = unique_text(b"replacement-")

		with storage_v2(False):
			file = self.legacy_file(original, label="rollback-content")
			path = file.get_full_path()

			# a fresh instance has no new_file flag, so the write is an update
			fresh = frappe.get_doc("File", file.name)
			fresh.save_file(content=replacement, overwrite=True)
			self.assertEqual(Path(path).read_bytes(), replacement)

			FileV1.on_rollback(fresh)
			self.assertEqual(Path(path).read_bytes(), original)
			self.assertIsNone(fresh.flags.get("original_content"))

	def test_rollback_moves_the_file_back_to_its_original_path(self):
		with storage_v2(False):
			file = self.legacy_file(unique_text(b"moved-"), label="rollback-path", is_private=0)
			public_path = get_files_path(file.file_name)
			private_path = get_files_path(file.file_name, is_private=1)
			self.remove_later(public_path)
			self.remove_later(private_path)

			fresh = frappe.get_doc("File", file.name)
			fresh.is_private = 1
			fresh.handle_is_private_changed()
			self.assertTrue(os.path.isfile(private_path))
			self.assertFalse(os.path.exists(public_path))

			FileV1.on_rollback(fresh)
			self.assertTrue(os.path.isfile(public_path))
			self.assertFalse(os.path.exists(private_path))
			self.assertIsNone(fresh.flags.get("original_path"))
