# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import os
from contextlib import contextmanager
from urllib.parse import quote

import frappe
from frappe.client import attach_file
from frappe.core.doctype.file.file_v2 import create_file_from_blob
from frappe.storage import get_driver, put_blob
from frappe.storage.blob import validate_upload
from frappe.storage.memory_driver import fake
from frappe.storage.tests import reset_file_controller
from frappe.tests import IntegrationTestCase

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEAK_USER = "storage-v2-weak-user@example.com"


@contextmanager
def storage_flag(value=1):
	"""Patch frappe.conf.storage_v2 for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf.storage_v2 = value
	reset_file_controller()
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_v2", None)
		else:
			frappe.conf.storage_v2 = previous
		reset_file_controller()


def unique_png():
	"""Unique PNG-sniffable bytes per call so dedup never collides across runs."""
	return PNG_MAGIC + frappe.generate_hash(length=32).encode()


def unique_html():
	return b"<!DOCTYPE html><html><body>" + frappe.generate_hash(length=32).encode() + b"</body></html>"


class TestFileStorageIntegration(IntegrationTestCase):
	def make_file(self, content, file_name="storage-v2.png", is_private=0, **kwargs):
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"content": content,
				"is_private": is_private,
				**kwargs,
			}
		).insert()
		self.delete_later("File", file.name)
		if file.get("blob"):
			self.delete_later("File Blob", file.blob)
		return file

	def delete_later(self, doctype, name):
		self.addCleanup(
			frappe.delete_doc, doctype, name, force=1, ignore_permissions=True, ignore_missing=True
		)

	def test_upload_creates_blob_row_and_public_url(self):
		content = unique_png()
		with storage_flag(), fake() as store:
			file = self.make_file(content, "photo.PNG", is_private=0)

			self.assertTrue(file.blob)
			blob = frappe.get_doc("File Blob", file.blob)
			self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
			self.assertEqual(blob.status, "Ready")
			self.assertEqual(blob.is_private, 0)
			# key carries a sanitized lowercase extension for nginx Content-Type
			self.assertTrue(blob.key.endswith(".png"))
			# the plain nginx path is local-driver-only; the memory driver has
			# no bytes on disk, so public rows get the /f/ route
			self.assertEqual(file.file_url, f"/f/{blob.name}/{quote(file.file_name)}")
			self.assertTrue(store.exists(blob.key, is_private=False))

	def test_upload_creates_private_f_url(self):
		content = unique_png()
		with storage_flag(), fake() as store:
			file = self.make_file(content, "my photo.png", is_private=1)

			blob = frappe.get_doc("File Blob", file.blob)
			self.assertEqual(blob.is_private, 1)
			self.assertEqual(file.file_url, f"/f/{blob.name}/{quote(file.file_name)}")
			self.assertTrue(store.exists(blob.key, is_private=True))

	def test_two_files_share_one_blob(self):
		content = unique_png()
		with storage_flag(), fake():
			first = self.make_file(content, "one.png")
			second = self.make_file(content, "two.png")

			self.assertNotEqual(first.name, second.name)
			self.assertEqual(first.blob, second.blob)
			self.assertEqual(
				frappe.db.count(
					"File Blob",
					{"checksum": hashlib.sha256(content).hexdigest(), "is_private": 0},
				),
				1,
			)

			# dedup is on content: a different claimed extension still returns
			# the first blob, extension and all
			deduped = put_blob(io.BytesIO(content), filename="other.gif")
			self.assertEqual(deduped.name, first.blob)
			self.assertTrue(deduped.key.endswith(".png"))

	def test_delete_file_keeps_bytes_and_blob(self):
		content = unique_png()
		with storage_flag(), fake() as store:
			file = self.make_file(content, "kept.png", is_private=1)
			blob = frappe.get_doc("File Blob", file.blob)

			file.delete()

			# GC owns the bytes; a File delete never removes them synchronously
			self.assertTrue(frappe.db.exists("File Blob", blob.name))
			self.assertTrue(store.exists(blob.key, is_private=True))

	def test_get_content_roundtrip(self):
		content = unique_png()
		with storage_flag(), fake():
			file = self.make_file(content, "roundtrip.png", is_private=1)

			fresh = frappe.get_doc("File", file.name)
			self.assertEqual(fresh.get_content(), content)

	def test_privacy_flip_repoints_blob(self):
		content = unique_png()
		with storage_flag(), fake() as store:
			file = self.make_file(content, "flip.png", is_private=0)
			old_blob_name = file.blob
			old_key = frappe.db.get_value("File Blob", old_blob_name, "key")

			file.is_private = 1
			file.save()
			self.delete_later("File Blob", file.blob)

			self.assertNotEqual(file.blob, old_blob_name)
			new_blob = frappe.get_doc("File Blob", file.blob)
			self.assertEqual(new_blob.is_private, 1)
			self.assertEqual(file.file_url, f"/f/{new_blob.name}/{quote(file.file_name)}")
			self.assertTrue(store.exists(new_blob.key, is_private=True))
			# the old blob is left for GC
			self.assertTrue(frappe.db.exists("File Blob", old_blob_name))
			self.assertTrue(store.exists(old_key, is_private=False))

	def test_create_file_from_blob(self):
		content = unique_png()
		with storage_flag(), fake():
			blob = put_blob(io.BytesIO(content), is_private=True, filename="direct.png")
			self.delete_later("File Blob", blob.name)

			todo = frappe.get_doc(doctype="ToDo", description="storage v2 blob attach target").insert()
			self.delete_later("ToDo", todo.name)

			file = create_file_from_blob(
				blob,
				"direct.png",
				attached_to_doctype="ToDo",
				attached_to_name=todo.name,
				is_private=True,
			)
			self.delete_later("File", file.name)

			self.assertEqual(file.blob, blob.name)
			self.assertEqual(file.file_size, blob.file_size)
			self.assertEqual(file.file_url, f"/f/{blob.name}/direct.png")
			# attachment comment parity with the regular upload path
			self.assertTrue(
				frappe.get_all(
					"Comment",
					filters={
						"reference_doctype": "ToDo",
						"reference_name": todo.name,
						"comment_type": "Attachment",
					},
				)
			)

	def test_attach_file_requires_write_permission(self):
		self.make_weak_user()
		content = "storage v2 attach " + frappe.generate_hash(length=32)
		with storage_flag(), fake():
			with self.set_user(WEAK_USER):
				# read on Language is granted to All; write is not
				self.assertRaises(
					frappe.PermissionError,
					attach_file,
					filename="denied.txt",
					filedata=content,
					doctype="Language",
					docname="en",
					is_private=1,
				)

			# with write permission the same call succeeds
			file = attach_file(
				filename="allowed.txt",
				filedata=content,
				doctype="Language",
				docname="en",
				is_private=1,
			)
			self.delete_later("File", file.name)
			self.delete_later("File Blob", file.blob)
			self.assertTrue(file.blob)

	def make_weak_user(self):
		if not frappe.db.exists("User", WEAK_USER):
			frappe.get_doc(
				doctype="User",
				email=WEAK_USER,
				first_name="Storage Weak",
				send_welcome_email=0,
			).insert(ignore_permissions=True)

	def test_validate_upload(self):
		with storage_flag(), fake():
			png_blob = put_blob(io.BytesIO(unique_png()), filename="ok.png")
			self.delete_later("File Blob", png_blob.name)
			# matching png passes
			validate_upload(png_blob, "ok.png")

			html_blob = put_blob(io.BytesIO(unique_html()), filename="evil.png")
			self.delete_later("File Blob", html_blob.name)
			self.assertEqual(html_blob.mime_type, "text/html")
			# html bytes disguised as png are rejected
			self.assertRaises(frappe.ValidationError, validate_upload, html_blob, "evil.png")
			# the same bytes under an honest extension pass
			validate_upload(html_blob, "page.html")

	def test_get_full_path_local_driver(self):
		content = unique_png()
		with storage_flag():
			file = self.make_file(content, "on-disk.png", is_private=1)
			blob = frappe.get_doc("File Blob", file.blob)
			driver = get_driver("local")
			self.addCleanup(driver.delete, blob.key, is_private=True)

			path = file.get_full_path()
			self.assertTrue(os.path.isfile(path))
			with open(path, "rb") as f:
				self.assertEqual(f.read(), content)
			self.assertTrue(file.exists_on_disk())

	def test_get_full_path_raises_for_non_local_driver(self):
		with storage_flag(), fake():
			file = self.make_file(unique_png(), "in-memory.png")
			self.assertRaises(frappe.ValidationError, file.get_full_path)

	def test_standard_write_path_rejects_disguised_html(self):
		# the sniff check runs on File.insert with content, not only in finish_upload
		with storage_flag(), fake():
			self.assertRaises(
				frappe.ValidationError,
				self.make_file,
				unique_html(),
				"disguised.png",
			)

	def test_public_file_url_on_local_driver(self):
		content = unique_png()
		with storage_flag():
			file = self.make_file(content, "local-public.png", is_private=0)
			blob = frappe.get_doc("File Blob", file.blob)
			driver = get_driver("local")
			self.addCleanup(driver.delete, blob.key, is_private=False)

			# local driver: bytes are on disk under public/files/blobs, so the
			# plain nginx path applies
			self.assertEqual(file.file_url, f"/files/blobs/{blob.key}")

	def test_copied_row_adopts_blob_from_f_url(self):
		# amend of a submittable doc rebuilds attachments from bare file_url;
		# a /f/ URL must relink the blob instead of failing validation
		content = unique_png()
		with storage_flag(), fake():
			original = self.make_file(content, "amended.png", is_private=1)

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

	def test_backfilled_row_saves_with_legacy_url(self):
		import os

		from frappe.storage import backfill
		from frappe.utils import get_files_path, now_datetime

		content = unique_png()
		filename = f"storage-v2-bf-{frappe.generate_hash(length=10)}.png"
		path = get_files_path(filename, is_private=1)
		with open(path, "wb") as f:
			f.write(content)
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

		doc = frappe.new_doc("File")
		doc.update(
			{
				"file_name": filename,
				"file_url": f"/private/files/{filename}",
				"is_private": 1,
				"is_folder": 0,
			}
		)
		doc.name = frappe.generate_hash(length=10)
		doc.owner = doc.modified_by = "Administrator"
		doc.creation = doc.modified = now_datetime()
		doc.db_insert()
		self.delete_later("File", doc.name)

		with storage_flag():
			backfill.run(filters={"name": doc.name})
			linked = frappe.get_doc("File", doc.name)
			self.delete_later("File Blob", linked.blob)
			self.assertTrue(linked.blob)
			self.assertEqual(linked.file_url, f"/private/files/{filename}")

			# saving a backfilled row must not fail URL validation
			linked.save()
			self.assertEqual(linked.file_url, f"/private/files/{filename}")

	def test_file_manager_save_file_creates_blob(self):
		from frappe.utils.file_manager import save_file

		content = unique_png()
		with storage_flag(), fake() as store:
			file = save_file(f"fm-{frappe.generate_hash(length=8)}.png", content, None, None, is_private=1)
			self.delete_later("File", file.name)
			self.delete_later("File Blob", file.blob)

			self.assertTrue(file.blob)
			blob = frappe.get_doc("File Blob", file.blob)
			self.assertTrue(store.exists(blob.key, is_private=True))

	def test_flag_off_is_legacy(self):
		content = unique_png()
		with storage_flag(0):
			file = self.make_file(content, "legacy.png", is_private=0)

			self.assertFalse(file.get("blob"))
			self.assertTrue(file.file_url.startswith("/files/"))
			self.assertFalse(file.file_url.startswith("/files/blobs/"))
			self.assertFalse(frappe.db.exists("File Blob", {"checksum": hashlib.sha256(content).hexdigest()}))

	# --- storage seams and controller resolution ---

	def test_base_file_class_has_no_storage_implementation(self):
		"""Every storage seam on the base File class refuses to run."""
		from frappe.core.doctype.file.file import File as BaseFile

		doc = BaseFile({"doctype": "File", "file_name": "unresolved.txt"})
		seams = (
			"_ingest_new_content",
			"_read_content",
			"_store_content",
			"get_full_path",
			"exists_on_disk",
			"validate_file_path",
			"validate_file_url",
			"validate_file_on_disk",
			"handle_is_private_changed",
			"_delete_file_on_disk",
		)
		for seam in seams:
			with self.subTest(seam=seam):
				with self.assertRaises(NotImplementedError) as caught:
					getattr(doc, seam)()
				self.assertIn("resolve_controller", str(caught.exception))

		# the one seam with a real default: keeping nothing is valid
		self.assertIsNone(doc._stash_original_content())

	def test_resolve_controller_splices_app_override(self):
		"""An app subclass of File keeps its methods on top of the storage class."""
		from frappe.core.doctype.file.file import File as BaseFile
		from frappe.core.doctype.file.file import _ResolvedFileMeta
		from frappe.core.doctype.file.file_v1 import FileV1
		from frappe.core.doctype.file.file_v2 import FileV2

		class AppFile(BaseFile):
			pass

		with storage_flag(1):
			self.assertIs(BaseFile.resolve_controller(), FileV2)
			# a class that already is a storage class is returned untouched
			self.assertIs(FileV2.resolve_controller(), FileV2)

			spliced = AppFile.resolve_controller()
			self.assertIsInstance(spliced, _ResolvedFileMeta)
			self.assertEqual(spliced.__name__, "AppFile")
			self.assertEqual(spliced.__mro__[:4], (spliced, AppFile, FileV2, BaseFile))

		with storage_flag(0):
			self.assertIs(BaseFile.resolve_controller(), FileV1)
			self.assertIs(FileV1.resolve_controller(), FileV1)

			spliced_v1 = AppFile.resolve_controller()
			self.assertEqual(spliced_v1.__mro__[:4], (spliced_v1, AppFile, FileV1, BaseFile))

	def test_resolved_file_class_is_picklable(self):
		"""A runtime-spliced File class pickles as the site's File controller."""
		import pickle

		from frappe.core.doctype.file.file import File as BaseFile
		from frappe.model.base_document import get_controller

		class AppFile(BaseFile):
			pass

		with storage_flag():
			spliced = AppFile.resolve_controller()

			self.assertIs(pickle.loads(pickle.dumps(spliced)), get_controller("File"))

			doc = spliced({"doctype": "File", "file_name": "picklable.txt"})
			restored = pickle.loads(pickle.dumps(doc))
			self.assertEqual(restored.file_name, "picklable.txt")
			self.assertIs(type(restored), get_controller("File"))

	def test_get_content_falls_back_to_next_encoding(self):
		"""Text that is not utf-8 is decoded with the next candidate encoding."""
		content = "café ".encode("windows-1250") + frappe.generate_hash(length=16).encode()
		with storage_flag(), fake():
			file = self.make_file(content, "latin.txt", is_private=1)

			fresh = frappe.get_doc("File", file.name)
			self.assertEqual(fresh.get_content(), content.decode("windows-1250"))

	# --- FileV2 branches ---

	def test_remote_file_stores_no_bytes(self):
		with storage_flag(), fake() as store:
			file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "remote.png",
					"file_url": "https://example.com/remote.png",
					"is_private": 0,
				}
			).insert()
			self.delete_later("File", file.name)

			self.assertFalse(file.get("blob"))
			self.assertEqual(file.file_url, "https://example.com/remote.png")
			self.assertFalse(store.blobs)
			# every byte-facing seam is a no-op for a remote reference
			self.assertIsNone(file.validate_file_path())
			self.assertIsNone(file.validate_file_url())
			self.assertIsNone(file.handle_is_private_changed())
			self.assertTrue(file.validate_file_on_disk())

	def test_handle_is_private_changed_ignores_unchanged_privacy(self):
		"""A doc rebuilt from a dict must not repoint its blob without a real change."""
		with storage_flag(), fake():
			file = self.make_file(unique_png(), "unchanged.png", is_private=1)
			blob_before = file.blob

			file.handle_is_private_changed()

			self.assertEqual(file.blob, blob_before)

	def test_before_save_reasserts_blob_privacy(self):
		"""A row whose privacy drifted from its blob is repointed on save."""
		with storage_flag(), fake() as store:
			file = self.make_file(unique_png(), "drifted.png", is_private=0)
			old_blob = file.blob

			# simulate a subclass that flipped is_private without going through
			# validate(): the row is now private but the blob is still public
			frappe.db.set_value("File", file.name, "is_private", 1, update_modified=False)

			doc = frappe.get_doc("File", file.name)
			doc.save()
			self.delete_later("File Blob", doc.blob)

			self.assertNotEqual(doc.blob, old_blob)
			new_blob = frappe.get_doc("File Blob", doc.blob)
			self.assertEqual(new_blob.is_private, 1)
			self.assertEqual(doc.file_url, f"/f/{new_blob.name}/{quote('drifted.png')}")
			self.assertTrue(store.exists(new_blob.key, is_private=True))

	def test_validate_file_url_rejects_unknown_prefix(self):
		with storage_flag(), fake():
			file = self.make_file(unique_png(), "prefix.png", is_private=1)

			file.file_url = "/somewhere/else.png"
			self.assertRaises(frappe.ValidationError, file.validate_file_url)

	def test_validate_file_on_disk_throws_when_bytes_are_gone(self):
		with storage_flag(), fake() as store:
			file = self.make_file(unique_png(), "vanished.png", is_private=1)
			blob = frappe.get_doc("File Blob", file.blob)

			store.delete(blob.key, is_private=True)

			self.assertFalse(file.exists_on_disk())
			self.assertRaises(OSError, file.validate_file_on_disk)

	def test_unbackfilled_legacy_row_reads_through_v1(self):
		"""storage_v2 on, blob still NULL: reads fall back to the disk path."""
		content = unique_png()
		name, path = self.make_legacy_row(content)

		with storage_flag():
			doc = frappe.get_doc("File", name)
			self.assertFalse(doc.get("blob"))

			# compat shim: every seam delegates to FileV1 while blob is NULL
			self.assertIsNone(doc.validate_file_path())
			self.assertIsNone(doc.validate_file_url())
			self.assertIsNone(doc.validate_file_on_disk())
			self.assertTrue(doc.exists_on_disk())
			self.assertEqual(doc.get_full_path(), path)
			self.assertEqual(doc.get_content(), content)

	def make_legacy_row(self, content, is_private=1):
		"""Insert a v1 File row with bytes on disk and no blob link."""
		from frappe.utils import get_files_path, now_datetime

		filename = f"storage-v2-legacy-{frappe.generate_hash(length=10)}.png"
		path = get_files_path(filename, is_private=is_private)
		with open(path, "wb") as f:
			f.write(content)
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

		doc = frappe.new_doc("File")
		doc.update(
			{
				"file_name": filename,
				"file_url": f"/private/files/{filename}" if is_private else f"/files/{filename}",
				"is_private": is_private,
				"is_folder": 0,
			}
		)
		doc.name = frappe.generate_hash(length=10)
		doc.owner = doc.modified_by = "Administrator"
		doc.creation = doc.modified = now_datetime()
		doc.db_insert()
		self.delete_later("File", doc.name)
		return doc.name, path

	def test_create_file_from_blob_accepts_a_blob_name(self):
		with storage_flag(), fake():
			blob = put_blob(io.BytesIO(unique_png()), is_private=True, filename="by-name.png")
			self.delete_later("File Blob", blob.name)

			file = create_file_from_blob(blob.name, "by-name.png", is_private=True)
			self.delete_later("File", file.name)

			self.assertEqual(file.blob, blob.name)
			self.assertEqual(file.file_url, f"/f/{blob.name}/by-name.png")

	def test_create_file_from_blob_rejects_pending_blob(self):
		with storage_flag(), fake():
			pending = frappe.get_doc(
				{
					"doctype": "File Blob",
					"key": f"pending/{frappe.generate_hash(length=16)}",
					"checksum": frappe.generate_hash(length=64),
					"driver": "memory",
					"file_size": 1,
					"is_private": 1,
					"status": "Pending",
				}
			).insert()
			self.delete_later("File Blob", pending.name)

			self.assertRaises(
				frappe.ValidationError,
				create_file_from_blob,
				pending.name,
				"pending.png",
				is_private=True,
			)

	def test_create_file_from_blob_rejects_privacy_mismatch(self):
		with storage_flag(), fake():
			blob = put_blob(io.BytesIO(unique_png()), is_private=True, filename="mismatch.png")
			self.delete_later("File Blob", blob.name)

			self.assertRaises(
				frappe.ValidationError,
				create_file_from_blob,
				blob,
				"mismatch.png",
				is_private=False,
			)

	def test_create_file_from_blob_adds_comment_without_after_insert(self):
		"""A subclass that overrides after_insert still gets the attachment comment."""
		from unittest.mock import patch

		from frappe.model.base_document import get_controller

		with storage_flag(), fake():
			blob = put_blob(io.BytesIO(unique_png()), is_private=True, filename="silent.png")
			self.delete_later("File Blob", blob.name)

			todo = frappe.get_doc(doctype="ToDo", description="storage v2 silent after_insert").insert()
			self.delete_later("ToDo", todo.name)

			controller = get_controller("File")
			with patch.object(controller, "after_insert", lambda self: None):
				file = create_file_from_blob(
					blob,
					"silent.png",
					attached_to_doctype="ToDo",
					attached_to_name=todo.name,
					is_private=True,
				)
			self.delete_later("File", file.name)

			self.assertTrue(
				frappe.get_all(
					"Comment",
					filters={
						"reference_doctype": "ToDo",
						"reference_name": todo.name,
						"comment_type": "Attachment",
					},
				)
			)

	# --- File Blob schema hook ---

	def test_file_blob_on_doctype_update(self):
		from unittest.mock import patch

		from frappe.core.doctype.file_blob.file_blob import on_doctype_update

		# the unique index already exists on a migrated site; add_unique is a no-op
		on_doctype_update()

		# a backend that cannot build the index must not break migrate
		with patch.object(type(frappe.local.db), "add_unique", side_effect=Exception("no unique index here")):
			on_doctype_update()
