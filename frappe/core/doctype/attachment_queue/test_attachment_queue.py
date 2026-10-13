# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from pathlib import Path

import frappe
from frappe.core.doctype.attachment_queue.attachment_queue import extract_attachment_text
from frappe.tests import IntegrationTestCase
from frappe.utils.file_manager import save_file

TEST_USER = "test@example.com"
TARGET_DOCTYPE = "ToDo"
DISABLED_DOCTYPE = "Note"


def pdf_with_text(text: str) -> bytes:
	"""Build a one page PDF carrying a real text layer, so there is something to extract."""
	content = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()
	objects = [
		b"<</Type/Catalog/Pages 2 0 R>>",
		b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
		b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
		b"<</Length %d>>stream\n%s\nendstream" % (len(content), content),
		b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
	]

	pdf = bytearray(b"%PDF-1.4\n")
	offsets = []
	for number, body in enumerate(objects, start=1):
		offsets.append(len(pdf))
		pdf += b"%d 0 obj" % number + body + b"endobj\n"

	startxref = len(pdf)
	pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
	for offset in offsets:
		pdf += b"%010d 00000 n \n" % offset
	pdf += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (
		len(objects) + 1,
		startxref,
	)
	return bytes(pdf)


class TestAttachmentQueue(IntegrationTestCase):
	def setUp(self):
		self.enable_upload_first(TARGET_DOCTYPE)

	def enable_upload_first(self, doctype: str):
		frappe.db.set_value("DocType", doctype, "enable_upload_first_workflow", 1)
		frappe.clear_cache(doctype=doctype)
		self.addCleanup(frappe.clear_cache, doctype=doctype)

	def make_file(self, content: bytes, file_name: str):
		return save_file(file_name, content, None, None, is_private=1)

	def make_queue(self, file_url: str):
		return frappe.get_doc(
			{
				"doctype": "Attachment Queue",
				"source_file": file_url,
				"document_type": TARGET_DOCTYPE,
			}
		).insert()

	def delete_committed(self, queue_name: str, task_name: str, file_url: str):
		# Everything this removes was committed on purpose, so removing it has to be too.
		frappe.db.rollback()

		for doctype, name in (("Attachment Queue", queue_name), ("Background Task", task_name)):
			if name and frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

		for name in frappe.get_all("File", filters={"file_url": file_url}, pluck="name"):
			frappe.delete_doc("File", name, force=True, ignore_permissions=True)

		frappe.db.set_value("DocType", TARGET_DOCTYPE, "enable_upload_first_workflow", 0)
		frappe.db.commit()  # nosemgrep
		frappe.clear_cache(doctype=TARGET_DOCTYPE)

	def test_saving_a_pdf_queues_extraction_and_stores_its_text(self):
		with self.set_user(TEST_USER):
			file_doc = self.make_file(pdf_with_text("INV-2026-0042"), "invoice.pdf")
			queue_doc = self.make_queue(file_doc.file_url)

			self.assertEqual(queue_doc.status, "Queued")
			self.assertTrue(queue_doc.task)
			self.assertTrue(queue_doc.extraction_queued_on)

			extract_attachment_text(queue_doc.name)
			queue_doc.reload()

			self.assertEqual(queue_doc.status, "Completed")
			self.assertEqual(queue_doc.extraction_method, "PDF Text Layer")
			self.assertIn("INV-2026-0042", queue_doc.extracted_text)
			self.assertFalse(queue_doc.error_message)

	def test_a_failed_extraction_records_the_reason(self):
		with self.set_user(TEST_USER):
			file_doc = self.make_file(pdf_with_text("BROKEN"), "broken.pdf")
			queue_doc = self.make_queue(file_doc.file_url)

		# File parses every PDF it stores, so the file can only be damaged once stored.
		Path(file_doc.get_full_path()).write_bytes(b"no longer a pdf")

		# Cancelling before the commit stops enqueue_task from handing a real job to a
		# worker, which would later run against the row this test removes.
		frappe.db.set_value("Background Task", queue_doc.task, "status", "Cancelled")

		# Extraction rolls back before recording the failure, so the row has to be
		# committed first, the way it already is when a worker picks it up.
		frappe.db.commit()  # nosemgrep
		self.addCleanup(self.delete_committed, queue_doc.name, queue_doc.task, file_doc.file_url)

		with self.assertRaises(Exception):
			extract_attachment_text(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Failed")
		self.assertTrue(queue_doc.error_message)
		self.assertFalse(queue_doc.extracted_text)

	def test_replacing_the_source_file_queues_a_fresh_extraction(self):
		with self.set_user(TEST_USER):
			first_file = self.make_file(pdf_with_text("FIRST FILE"), "first.pdf")
			queue_doc = self.make_queue(first_file.file_url)

			extract_attachment_text(queue_doc.name)
			queue_doc.reload()
			self.assertEqual(queue_doc.status, "Completed")
			first_task = queue_doc.task

			second_file = self.make_file(pdf_with_text("SECOND FILE"), "second.pdf")
			queue_doc.source_file = second_file.file_url
			queue_doc.save()
			queue_doc.reload()

			self.assertEqual(queue_doc.status, "Queued")
			self.assertNotEqual(queue_doc.task, first_task)
			self.assertFalse(queue_doc.extracted_text)
			self.assertFalse(queue_doc.extraction_method)

	def test_a_doctype_without_the_workflow_enabled_is_rejected(self):
		# The target is checked before the file is, so this needs no uploaded file.
		with self.set_user(TEST_USER):
			queue_doc = frappe.get_doc(
				{
					"doctype": "Attachment Queue",
					"source_file": "/private/files/never-read.pdf",
					"document_type": DISABLED_DOCTYPE,
				}
			)
			self.assertRaisesRegex(
				frappe.ValidationError,
				"does not allow document creation",
				queue_doc.insert,
			)

	def test_a_private_file_cannot_be_queued_without_read_permission(self):
		# Owned by Administrator and attached to nothing, so File permission denies it.
		file_doc = self.make_file(pdf_with_text("CONFIDENTIAL"), "private.pdf")

		with self.set_user(TEST_USER):
			queue_doc = frappe.get_doc(
				{
					"doctype": "Attachment Queue",
					"source_file": file_doc.file_url,
					"document_type": TARGET_DOCTYPE,
				}
			)
			self.assertRaises(frappe.PermissionError, queue_doc.insert)
