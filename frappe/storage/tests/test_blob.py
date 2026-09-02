# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
from unittest.mock import patch

import frappe
from frappe.storage import put_blob
from frappe.storage.blob import (
	SPOOL_MAX_MEMORY,
	make_key,
	sha256_of,
	sniff_mime,
	spool_to_tempfile,
	validate_upload,
)
from frappe.storage.memory_driver import fake
from frappe.tests import IntegrationTestCase

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def unique_content(prefix=b"storage-v2-blob-test-"):
	"""Unique bytes per call so dedup never collides across tests or runs."""
	return prefix + frappe.generate_hash(length=32).encode()


class TestPutBlob(IntegrationTestCase):
	def put(self, content: bytes, is_private: bool = False):
		blob = put_blob(io.BytesIO(content), is_private=is_private)
		self.addCleanup(
			frappe.delete_doc, "File Blob", blob.name, force=1, ignore_permissions=True, ignore_missing=True
		)
		return blob

	def test_dedup_returns_same_blob_for_same_bytes_and_privacy(self):
		content = unique_content()
		with fake():
			first = self.put(content, is_private=True)
			second = self.put(content, is_private=True)

			self.assertEqual(first.name, second.name)
			self.assertEqual(frappe.db.count("File Blob", {"checksum": first.checksum, "is_private": 1}), 1)

	def test_public_and_private_get_distinct_blobs(self):
		content = unique_content()
		with fake() as store:
			public = self.put(content, is_private=False)
			private = self.put(content, is_private=True)

			self.assertNotEqual(public.name, private.name)
			# key derives from content alone, so both rows share it
			self.assertEqual(public.key, private.key)
			self.assertEqual(public.is_private, 0)
			self.assertEqual(private.is_private, 1)
			self.assertTrue(store.exists(public.key, is_private=False))
			self.assertTrue(store.exists(private.key, is_private=True))

	def test_checksum_is_sha256_of_content(self):
		content = unique_content()
		with fake():
			blob = self.put(content)
		self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())

	def test_mime_sniffed_from_bytes_not_filename(self):
		# PNG magic bytes are detected even if the client would claim a .txt name
		png = PNG_MAGIC + unique_content(prefix=b"")
		text = unique_content(prefix=b"plain text claimed as a.txt ")
		with fake():
			self.assertEqual(self.put(png).mime_type, "image/png")
			self.assertEqual(self.put(text).mime_type, "application/octet-stream")

	def test_key_layout(self):
		content = unique_content()
		with fake():
			blob = self.put(content)
		checksum = blob.checksum
		self.assertEqual(blob.key, f"{checksum[:2]}/{checksum[2:4]}/{checksum}")
		self.assertEqual(blob.key, make_key(checksum))

	def test_blob_row_fields(self):
		content = unique_content()
		with fake() as store:
			blob = self.put(content, is_private=True)

			self.assertEqual(blob.doctype, "File Blob")
			self.assertEqual(blob.driver, "memory")
			self.assertEqual(blob.file_size, len(content))
			self.assertEqual(blob.status, "Ready")
			self.assertEqual(blob.is_private, 1)
			self.assertTrue(blob.name)

			# bytes actually landed in the driver under the key
			with store.read(blob.key, is_private=True) as stream:
				self.assertEqual(stream.read(), content)

	def test_rolled_back_write_deletes_bytes(self):
		# a rolled-back File Blob row must not leave unreachable bytes behind
		content = unique_content(b"rollback-")
		with fake() as store:
			blob = put_blob(io.BytesIO(content))
			key = blob.key
			self.assertTrue(store.exists(key))

			frappe.db.rollback()

			self.assertFalse(frappe.db.exists("File Blob", blob.name))
			self.assertFalse(store.exists(key))

	def test_validate_upload_rejects_pdf_with_javascript(self):
		# legacy File.check_content parity on the finish_upload path
		pdf = b"%PDF-1.4\n" + unique_content(prefix=b"")
		with fake():
			blob = self.put(pdf)
			self.assertEqual(blob.mime_type, "application/pdf")

			with patch("frappe.utils.pdf.pdf_contains_js", return_value=True):
				self.assertRaises(frappe.ValidationError, validate_upload, blob, "doc.pdf")
			with patch("frappe.utils.pdf.pdf_contains_js", return_value=False):
				validate_upload(blob, "doc.pdf")

	def test_multi_megabyte_stream(self):
		# well past SPOOL_MAX_MEMORY, so the spool spills to disk
		content = unique_content() + b"\x00\xff" * (2 * 1024 * 1024)
		self.assertGreater(len(content), SPOOL_MAX_MEMORY)
		with fake() as store:
			blob = self.put(content, is_private=True)

			self.assertEqual(blob.file_size, len(content))
			self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
			with store.read(blob.key, is_private=True) as stream:
				self.assertEqual(stream.read(), content)


class TestBlobHelpers(IntegrationTestCase):
	def test_spool_spills_large_input_to_disk(self):
		content = b"a" * (SPOOL_MAX_MEMORY + 1)
		spool, size = spool_to_tempfile(io.BytesIO(content))
		with spool:
			self.assertEqual(size, len(content))
			# SpooledTemporaryFile rolled over: content is on disk, not in RAM
			self.assertTrue(spool._rolled)
			self.assertEqual(spool.read(), content)

	def test_spool_keeps_small_input_in_memory(self):
		content = b"small"
		spool, size = spool_to_tempfile(io.BytesIO(content))
		with spool:
			self.assertEqual(size, len(content))
			self.assertFalse(spool._rolled)
			self.assertEqual(spool.read(), content)

	def test_sha256_of_reads_from_start_and_rewinds(self):
		content = b"hello world"
		stream = io.BytesIO(content)
		stream.seek(5)
		self.assertEqual(sha256_of(stream), hashlib.sha256(content).hexdigest())
		self.assertEqual(stream.tell(), 0)

	def test_sniff_mime_rewinds_stream(self):
		stream = io.BytesIO(PNG_MAGIC + b"rest of file")
		self.assertEqual(sniff_mime(stream), "image/png")
		self.assertEqual(stream.tell(), 0)
