# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import os
from contextlib import contextmanager
from urllib.parse import quote

import frappe
from frappe.client import attach_file
from frappe.core.doctype.file.file import create_file_from_blob
from frappe.storage import get_driver, put_blob
from frappe.storage.blob import validate_upload
from frappe.storage.memory_driver import fake
from frappe.tests import IntegrationTestCase

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEAK_USER = "storage-v2-weak-user@example.com"


@contextmanager
def storage_flag(value=1):
	"""Patch frappe.conf.storage_v2 for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf.storage_v2 = value
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_v2", None)
		else:
			frappe.conf.storage_v2 = previous


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
			self.assertEqual(file.file_url, f"/files/blobs/{blob.key}")
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

	def test_flag_off_is_legacy(self):
		content = unique_png()
		with storage_flag(0):
			file = self.make_file(content, "legacy.png", is_private=0)

			self.assertFalse(file.get("blob"))
			self.assertTrue(file.file_url.startswith("/files/"))
			self.assertFalse(file.file_url.startswith("/files/blobs/"))
			self.assertFalse(
				frappe.db.exists("File Blob", {"checksum": hashlib.sha256(content).hexdigest()})
			)
