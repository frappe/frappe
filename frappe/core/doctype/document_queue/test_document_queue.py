import subprocess
from unittest.mock import patch
from uuid import uuid4

from pypdf import PdfWriter

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.file_manager import save_file


class FakePDFPlumber:
	def __init__(self, pages):
		self.pages = pages

	def open(self, file_path):
		return FakePDF(self.pages)


class FakePDF:
	def __init__(self, pages):
		self.pages = pages

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc, traceback):
		return False


class FakeCorruptPDFPlumber:
	def open(self, file_path):
		raise ValueError("corrupt pdf structure")


class FakePDFPage:
	width = 612
	height = 792

	def __init__(self, text="", layout_text="", words=None, tables=None):
		self.text = text
		self.layout_text = layout_text
		self.words = words or []
		self.tables = tables or []

	def extract_text(self, layout=False):
		return self.layout_text if layout else self.text

	def extract_words(self, **kwargs):
		return self.words

	def extract_tables(self):
		return self.tables


class TestDocumentQueue(IntegrationTestCase):
	def make_file(self, file_name=None, content=None):
		file_name = file_name or f"document-{uuid4().hex}.pdf"
		content = content if content is not None else self.make_pdf_content()
		file_doc = save_file(file_name, content, None, None, is_private=1)
		self.addCleanup(lambda: frappe.delete_doc("File", file_doc.name, force=True, ignore_permissions=True))
		return file_doc

	def make_queue(self, file_name=None, content=None, auto_extract=False, document_type="File"):
		file_doc = self.make_file(file_name, content)
		queue_doc = frappe.get_doc(
			{"doctype": "Document Queue", "source_file": file_doc.file_url, "document_type": document_type}
		)
		if not auto_extract:
			queue_doc.flags.skip_auto_extraction = True
		queue_doc.insert()
		self.addCleanup(
			lambda: frappe.delete_doc("Document Queue", queue_doc.name, force=True, ignore_permissions=True)
		)
		return queue_doc

	def make_desk_user(self):
		email = f"document-queue-user-{uuid4().hex}@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Document Queue",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		user.add_roles("Desk User")
		self.addCleanup(lambda: frappe.delete_doc("User", user.name, force=True, ignore_permissions=True))
		return user

	def make_target_doctype(self, **desk_user_permissions):
		"""An upload-first target DocType whose Desk User permissions the test controls.

		"File" is unusable for this: it grants the "All" role blanket read/write/create,
		so it can never express "user cannot create the target".
		"""
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		# DocPerm defaults read/write/create/delete to 1, so an omitted right is a granted
		# right. Start from nothing and let the caller opt in to exactly what it needs.
		rights = {"read": 0, "write": 0, "create": 0, "delete": 0}
		rights.update(desk_user_permissions)

		doctype = new_doctype(
			enable_upload_first_workflow=1,
			permissions=[{"role": "Desk User", **rights}],
		).insert(ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.delete_doc("DocType", doctype.name, force=True, ignore_permissions=True)
		)
		return doctype.name

	def enable_upload_first_workflow(self, doctype="File"):
		original = frappe.db.get_value("DocType", doctype, "enable_upload_first_workflow")
		frappe.db.set_value("DocType", doctype, "enable_upload_first_workflow", 1)
		self.addCleanup(
			lambda: frappe.db.set_value("DocType", doctype, "enable_upload_first_workflow", original)
		)

	def make_pdf_content(self):
		from io import BytesIO

		buffer = BytesIO()
		writer = PdfWriter()
		writer.add_metadata({"/Subject": uuid4().hex})
		writer.add_blank_page(width=612, height=792)
		writer.write(buffer)
		return buffer.getvalue()

	def test_creates_document_queue_record(self):
		queue_doc = self.make_queue()

		self.assertEqual(queue_doc.status, "Draft")
		self.assertTrue(queue_doc.source_file.endswith(".pdf"))

	def test_queues_extraction_when_document_queue_record_is_created(self):
		with patch(
			"frappe.core.doctype.document_queue.document_queue.enqueue_document_extraction"
		) as enqueue_document_extraction:
			queue_doc = self.make_queue(auto_extract=True)

		enqueue_document_extraction.assert_called_once_with(
			queue_doc.name, queue="default", enqueue_after_commit=True
		)

	def test_does_not_requeue_extraction_when_unrelated_field_changes(self):
		queue_doc = self.make_queue()
		reloaded = frappe.get_doc("Document Queue", queue_doc.name)

		with patch(
			"frappe.core.doctype.document_queue.document_queue.enqueue_document_extraction"
		) as enqueue_document_extraction:
			reloaded.document_type = "File"
			reloaded.save()

		enqueue_document_extraction.assert_not_called()

	def test_does_not_requeue_extraction_while_in_progress_or_completed(self):
		queue_doc = self.make_queue()
		alternate_files = [self.make_file(), self.make_file()]

		for i, status in enumerate(("Queued", "Processing", "Completed")):
			queue_doc.db_set("status", status, update_modified=False)
			reloaded = frappe.get_doc("Document Queue", queue_doc.name)

			with patch(
				"frappe.core.doctype.document_queue.document_queue.enqueue_document_extraction"
			) as enqueue_document_extraction:
				# Alternate source_file so has_value_changed is True, isolating the status guard.
				reloaded.source_file = alternate_files[i % 2].file_url
				reloaded.save()

			enqueue_document_extraction.assert_not_called()

	def test_extracts_pdf_and_marks_ready_for_review(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		queue_doc = self.make_queue()
		pdfplumber = FakePDFPlumber(
			[
				FakePDFPage(
					text="Invoice text with enough useful embedded PDF text",
					layout_text="Invoice        Amount\n\nTotal          100.00",
					words=[
						{"text": "Invoice", "x0": 10, "top": 20, "x1": 50, "bottom": 30},
						{"text": "Amount", "x0": 420, "top": 23, "x1": 470, "bottom": 33},
						{"text": "Total", "x0": 10, "top": 75, "x1": 45, "bottom": 85},
						{"text": "100.00", "x0": 420, "top": 78, "x1": 465, "bottom": 88},
					],
					tables=[[["Header"], ["Value"]]],
				)
			]
		)

		with patch(
			"frappe.core.doctype.document_queue.document_queue._get_pdfplumber", return_value=pdfplumber
		):
			extract_document_queue_record(queue_doc.name)

		queue_doc.reload()
		raw = frappe.parse_json(queue_doc.raw_extraction_json)

		self.assertEqual(queue_doc.status, "Ready for Review")
		self.assertEqual(queue_doc.extraction_method, "pdfplumber")
		self.assertIn("Invoice", queue_doc.extracted_text)
		self.assertIn("Amount", queue_doc.extracted_text)
		self.assertIn("Total", queue_doc.extracted_text)
		self.assertIn("100.00", queue_doc.extracted_text)
		self.assertGreater(
			queue_doc.extracted_text.index("Amount"), queue_doc.extracted_text.index("Invoice")
		)
		self.assertRegex(queue_doc.extracted_text, r"Invoice\s+Amount")
		self.assertRegex(queue_doc.extracted_text, r"Total\s+100\.00")
		self.assertIn("\n", queue_doc.extracted_text)
		self.assertEqual(raw["pages"][0]["words"][0]["text"], "Invoice")
		self.assertEqual(raw["pages"][0]["layout_text"], "Invoice        Amount\n\nTotal          100.00")
		self.assertNotIn("grid_text", raw["pages"][0])
		self.assertEqual(raw["pages"][0]["tables"][0][0][0], "Header")
		self.assertTrue(queue_doc.extraction_started_on)
		self.assertTrue(queue_doc.extraction_completed_on)

	def test_marks_failed_for_unsupported_file(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		queue_doc = self.make_queue(
			file_name=f"document-{uuid4().hex}.txt",
			content=f"not a pdf {uuid4().hex}".encode(),
		)

		with self.assertRaises(Exception):
			extract_document_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Failed")
		self.assertIn("Only PDF and image extraction is supported", queue_doc.error_message)
		self.assertTrue(queue_doc.debug_output)

	def test_marks_failed_when_pdf_cannot_be_parsed(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		queue_doc = self.make_queue()

		with patch(
			"frappe.core.doctype.document_queue.document_queue._get_pdfplumber",
			return_value=FakeCorruptPDFPlumber(),
		):
			with self.assertRaises(Exception):
				extract_document_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Failed")
		self.assertIn("corrupt pdf structure", queue_doc.error_message)
		self.assertIn("Traceback", queue_doc.debug_output)
		self.assertFalse(queue_doc.extracted_text)
		self.assertFalse(queue_doc.raw_extraction_json)

	def test_requeue_clears_stale_error_after_failed_extraction(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		queue_doc = self.make_queue(
			file_name=f"document-{uuid4().hex}.txt",
			content=f"not a pdf {uuid4().hex}".encode(),
		)

		with self.assertRaises(Exception):
			extract_document_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Failed")
		self.assertTrue(queue_doc.error_message)

		# Retry must not let the prior failure linger next to the new result.
		queue_doc.mark_queued()
		queue_doc.reload()
		self.assertFalse(queue_doc.error_message)
		self.assertFalse(queue_doc.debug_output)

	def test_extracts_image_with_tesseract(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		queue_doc = self.make_queue(
			file_name=f"document-{uuid4().hex}.png",
			content=b"fake image content",
		)

		with patch(
			"frappe.core.doctype.document_queue.document_queue.extract_image_text_with_tesseract",
			return_value=(
				"Image OCR text",
				[{"text": "Image", "x0": 1, "top": 2, "x1": 20, "bottom": 10, "confidence": "95"}],
				["Image OCR mocked"],
			),
		):
			extract_document_queue_record(queue_doc.name)

		queue_doc.reload()
		raw = frappe.parse_json(queue_doc.raw_extraction_json)

		self.assertEqual(queue_doc.status, "Ready for Review")
		self.assertEqual(queue_doc.extraction_method, "tesseract")
		self.assertEqual(queue_doc.extracted_text, "Image OCR text")
		self.assertEqual(raw["pages"][0]["words"][0]["text"], "Image")
		self.assertIn("Image OCR mocked", queue_doc.debug_output)

	def test_ocr_fallback_can_be_used_when_embedded_text_is_weak(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		queue_doc = self.make_queue()
		pdfplumber = FakePDFPlumber([FakePDFPage(text="", layout_text="", words=[], tables=[])])

		with (
			patch(
				"frappe.core.doctype.document_queue.document_queue._get_pdfplumber", return_value=pdfplumber
			),
			patch(
				"frappe.core.doctype.document_queue.document_queue.extract_pdf_text_with_tesseract",
				return_value=("OCR fallback text from scanned PDF", ["OCR mocked"]),
			),
		):
			extract_document_queue_record(queue_doc.name)

		queue_doc.reload()
		raw = frappe.parse_json(queue_doc.raw_extraction_json)

		self.assertEqual(queue_doc.status, "Ready for Review")
		self.assertEqual(queue_doc.extraction_method, "pdfplumber+tesseract")
		self.assertEqual(queue_doc.extracted_text, "OCR fallback text from scanned PDF")
		self.assertEqual(raw["ocr_text"], "OCR fallback text from scanned PDF")
		self.assertIn("OCR mocked", queue_doc.debug_output)

	def test_completes_without_ocr_when_tesseract_unavailable(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		queue_doc = self.make_queue()
		pdfplumber = FakePDFPlumber([FakePDFPage(text="", layout_text="", words=[], tables=[])])

		# Scanned PDF with no embedded text, but the OCR toolchain isn't installed.
		with (
			patch(
				"frappe.core.doctype.document_queue.document_queue._get_pdfplumber", return_value=pdfplumber
			),
			patch("frappe.core.doctype.document_queue.document_queue.shutil.which", return_value=None),
		):
			extract_document_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Ready for Review")
		self.assertEqual(queue_doc.extraction_method, "pdfplumber")
		self.assertFalse(queue_doc.extracted_text)
		self.assertIn("OCR skipped", queue_doc.debug_output)

	def test_error_message_includes_ocr_tool_stderr_on_subprocess_failure(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		queue_doc = self.make_queue()
		pdfplumber = FakePDFPlumber([FakePDFPage(text="", layout_text="", words=[], tables=[])])
		failed_process = subprocess.CompletedProcess(
			args=["tesseract"], returncode=1, stdout="", stderr="Error opening data file eng.traineddata"
		)

		with (
			patch(
				"frappe.core.doctype.document_queue.document_queue._get_pdfplumber", return_value=pdfplumber
			),
			patch(
				"frappe.core.doctype.document_queue.document_queue.shutil.which", return_value="/usr/bin/tesseract"
			),
			patch(
				"frappe.core.doctype.document_queue.document_queue.subprocess.run", return_value=failed_process
			),
		):
			with self.assertRaises(Exception):
				extract_document_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Failed")
		self.assertIn("Error opening data file eng.traineddata", queue_doc.error_message)

	def test_ocr_fallback_boundary_at_twenty_characters(self):
		from frappe.core.doctype.document_queue.document_queue import extract_document_queue_record

		# 19 chars is "weak" text and should fall back to OCR; 20 is "useful" and should not.
		below_threshold = self.make_queue()
		pdfplumber = FakePDFPlumber([FakePDFPage(text="x" * 19, layout_text="x" * 19)])
		with (
			patch(
				"frappe.core.doctype.document_queue.document_queue._get_pdfplumber", return_value=pdfplumber
			),
			patch(
				"frappe.core.doctype.document_queue.document_queue.extract_pdf_text_with_tesseract",
				return_value=("OCR text", ["OCR mocked"]),
			) as extract_pdf_text_with_tesseract,
		):
			extract_document_queue_record(below_threshold.name)

		extract_pdf_text_with_tesseract.assert_called_once()
		below_threshold.reload()
		self.assertEqual(below_threshold.extraction_method, "pdfplumber+tesseract")

		at_threshold = self.make_queue()
		pdfplumber = FakePDFPlumber([FakePDFPage(text="x" * 20, layout_text="x" * 20)])
		with (
			patch(
				"frappe.core.doctype.document_queue.document_queue._get_pdfplumber", return_value=pdfplumber
			),
			patch(
				"frappe.core.doctype.document_queue.document_queue.extract_pdf_text_with_tesseract"
			) as extract_pdf_text_with_tesseract,
		):
			extract_document_queue_record(at_threshold.name)

		extract_pdf_text_with_tesseract.assert_not_called()
		at_threshold.reload()
		self.assertEqual(at_threshold.extraction_method, "pdfplumber")

	def test_desk_user_cannot_create_queue_row_directly(self):
		# Queue rows are framework-owned, like Email Queue: they are created for the user by
		# create_upload_first_queue(), never authored from a form.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1, create=1)

		with self.set_user(user.name):
			file_doc = self.make_file()
			queue_doc = frappe.get_doc(
				{
					"doctype": "Document Queue",
					"source_file": file_doc.file_url,
					"document_type": target_doctype,
				}
			)
			queue_doc.flags.skip_auto_extraction = True

			with self.assertRaises(frappe.PermissionError):
				queue_doc.insert()

	def test_upload_first_queue_requires_create_on_target_doctype(self):
		from frappe.core.doctype.document_queue.document_queue import create_upload_first_queue

		# The row is inserted with ignore_permissions, so create on the target DocType is
		# the check standing in for it.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1)

		with self.set_user(user.name):
			file_doc = self.make_file()

			with self.assertRaises(frappe.PermissionError):
				create_upload_first_queue(file_doc.name, target_doctype)

	def test_desk_user_can_create_upload_first_queue_for_permitted_target(self):
		from frappe.core.doctype.document_queue.document_queue import create_upload_first_queue

		# Counterpart to the test above: create on the target DocType is what unlocks it.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1, create=1)

		with self.set_user(user.name):
			file_doc = self.make_file()
			context = create_upload_first_queue(file_doc.name, target_doctype)

		self.addCleanup(
			lambda: frappe.delete_doc(
				"Document Queue", context["queue_name"], force=True, ignore_permissions=True
			)
		)
		queue_doc = frappe.get_doc("Document Queue", context["queue_name"])
		self.assertEqual(queue_doc.owner, user.name)
		self.assertEqual(queue_doc.document_type, target_doctype)
		self.assertEqual(queue_doc.status, "Queued")

	def test_owner_cannot_drive_queue_without_create_on_target_doctype(self):
		# A queue row outlives the permission that created it. Losing create on the target
		# must stop the owner driving the row, while leaving their read intact.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1)
		queue_doc = self.make_queue(document_type=target_doctype)
		queue_doc.db_set("owner", user.name, update_modified=False)
		queue_doc.reload()

		with self.set_user(user.name):
			self.assertTrue(frappe.has_permission("Document Queue", "read", doc=queue_doc))

			with patch.object(queue_doc, "enqueue_extraction") as enqueue_extraction:
				with self.assertRaises(frappe.PermissionError):
					queue_doc.extract_in_background()

			with self.assertRaises(frappe.PermissionError):
				queue_doc.set_document_type(target_doctype)

		enqueue_extraction.assert_not_called()

	def test_owner_can_drive_queue_with_create_on_target_doctype(self):
		# Counterpart to the test above, so the denial is attributable to the missing create
		# right and nothing else.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1, create=1)
		queue_doc = self.make_queue(document_type=target_doctype)
		queue_doc.db_set("owner", user.name, update_modified=False)
		queue_doc.reload()

		with self.set_user(user.name):
			with patch.object(queue_doc, "enqueue_extraction") as enqueue_extraction:
				queue_doc.extract_in_background()

			context = queue_doc.set_document_type(target_doctype)

		enqueue_extraction.assert_called_once()
		self.assertEqual(context["document_type"], target_doctype)

	def test_set_document_type_requires_upload_first_enabled_doctype(self):
		queue_doc = self.make_queue()

		with self.assertRaises(frappe.ValidationError):
			queue_doc.set_document_type("File")

		self.enable_upload_first_workflow("File")

		context = queue_doc.set_document_type("File")
		queue_doc.reload()

		self.assertEqual(queue_doc.document_type, "File")
		self.assertEqual(context["document_type"], "File")

	def test_create_upload_first_queue_queues_extraction_and_returns_review_context(self):
		from frappe.core.doctype.document_queue.document_queue import create_upload_first_queue

		self.enable_upload_first_workflow("File")
		file_doc = self.make_file()
		context = create_upload_first_queue(file_doc.name, "File")

		queue_doc = frappe.get_doc("Document Queue", context["queue_name"])
		self.addCleanup(
			lambda: frappe.delete_doc("Document Queue", queue_doc.name, force=True, ignore_permissions=True)
		)

		file_doc.reload()
		self.assertEqual(queue_doc.document_type, "File")
		self.assertEqual(queue_doc.status, "Queued")
		self.assertTrue(queue_doc.task)
		self.assertEqual(context["document_type"], "File")
		self.assertEqual(context["source_file"], file_doc.file_url)
		self.assertEqual(context["status"], "Queued")
		self.assertEqual(file_doc.attached_to_doctype, "Document Queue")
		self.assertEqual(file_doc.attached_to_name, queue_doc.name)

	def test_create_queue_without_file_write_permission(self):
		from frappe.core.doctype.document_queue.document_queue import create_upload_first_queue

		self.enable_upload_first_workflow("File")

		# Owned by Administrator, so the user below only gets what the share grants.
		file_doc = self.make_file()
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"document-queue-reader-{uuid4().hex}@example.com",
				"first_name": "Document Queue Reader",
				"send_welcome_email": 0,
				"roles": [{"role": "All"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("User", user.name, force=True, ignore_permissions=True))

		# Read but not write: enough to see the file, not enough to re-parent it onto a
		# queue row, which is what create_upload_first_queue does.
		frappe.share.add(doctype="File", name=file_doc.name, user=user.name, read=1, write=0)

		with self.set_user(user.name):
			with self.assertRaises(frappe.PermissionError):
				create_upload_first_queue(file_doc.name, "File")

	def test_get_document_review_context(self):
		from frappe.core.doctype.document_queue.document_queue import get_document_review_context

		queue_doc = self.make_queue()
		queue_doc.db_set(
			{
				"document_type": "File",
				"status": "Ready for Review",
				"extracted_text": "Layout text",
				"raw_extraction_json": frappe.as_json({"pages": [{"page_number": 1}]}),
			}
		)

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			context = get_document_review_context(queue_doc.name)

		self.assertEqual(context["queue_name"], queue_doc.name)
		self.assertEqual(context["document_type"], "File")
		self.assertTrue(context["source_file_url"].startswith(queue_doc.source_file))
		self.assertIn("fid=", context["source_file_url"])
		self.assertEqual(context["extracted_text"], "Layout text")
		# Only the developer-mode debug tab renders this, and it holds a box per word per
		# page, so it stays off the wire for everyone else.
		self.assertEqual(context["raw_extraction_json"], {})

		with patch.dict(frappe.conf, {"developer_mode": 1}):
			context = get_document_review_context(queue_doc.name)

		self.assertEqual(context["raw_extraction_json"]["pages"][0]["page_number"], 1)

	def test_review_context_carries_the_failure_reason(self):
		from frappe.core.doctype.document_queue.document_queue import get_document_review_context

		# The review panel shows this to whoever is reviewing a Failed row, so it has to
		# reach them regardless of developer mode.
		queue_doc = self.make_queue()
		queue_doc.db_set({"status": "Failed", "error_message": "Only PDF and image extraction"})

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			context = get_document_review_context(queue_doc.name)

		self.assertEqual(context["status"], "Failed")
		self.assertIn("Only PDF and image extraction", context["error_message"])

	def test_link_to_document_marks_completed(self):
		from frappe.core.doctype.document_queue.document_queue import link_to_document

		queue_doc = self.make_queue()
		target_file = self.make_file(file_name=f"target-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		result = link_to_document(queue_doc.name, "File", target_file.name)

		queue_doc.reload()
		self.assertTrue(result["ok"])
		self.assertEqual(queue_doc.status, "Completed")
		self.assertEqual(queue_doc.document_type, "File")
		self.assertEqual(queue_doc.created_document, target_file.name)

		source_file = frappe.get_doc("File", frappe.db.get_value("File", {"file_url": queue_doc.source_file}))
		self.assertEqual(source_file.attached_to_doctype, "File")
		self.assertEqual(source_file.attached_to_name, target_file.name)

	def test_link_to_document_rejects_mismatched_document_type(self):
		from frappe.core.doctype.document_queue.document_queue import link_to_document

		# The client can hold a queue name from an earlier, failed save. If it then saves an
		# unrelated document, this is the check that has to stop it. "Administrator" exists,
		# so the existence check cannot be what rejects the call.
		queue_doc = self.make_queue()
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		with self.assertRaises(frappe.ValidationError):
			link_to_document(queue_doc.name, "User", "Administrator")

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Ready for Review")
		self.assertFalse(queue_doc.created_document)

	def test_link_to_document_rejects_row_that_already_produced_a_document(self):
		from frappe.core.doctype.document_queue.document_queue import link_to_document

		queue_doc = self.make_queue()
		first_target = self.make_file(file_name=f"first-{uuid4().hex}.pdf")
		second_target = self.make_file(file_name=f"second-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		link_to_document(queue_doc.name, "File", first_target.name)

		# Re-linking moves the row on but not the source file, which is already attached to
		# the first document — the row and the file would end up pointing at different docs.
		with self.assertRaises(frappe.ValidationError):
			link_to_document(queue_doc.name, "File", second_target.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.created_document, first_target.name)

	def test_review_context_withholds_debug_output_from_non_privileged_owner(self):
		from frappe.core.doctype.document_queue.document_queue import get_document_review_context

		# debug_output is a traceback with local variable values. Being able to read the
		# queue row is not enough to earn it — permlevel 1 is.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1)
		queue_doc = self.make_queue(document_type=target_doctype)
		queue_doc.db_set(
			{
				"status": "Failed",
				"error_message": "extraction failed",
				"debug_output": "Traceback ... password_hash = 'leaked'",
				"owner": user.name,
			},
			update_modified=False,
		)

		self.assertIn("leaked", get_document_review_context(queue_doc.name)["debug_output"])

		with self.set_user(user.name):
			context = get_document_review_context(queue_doc.name)

		self.assertEqual(context["debug_output"], "")
		# The row itself stays readable; only the traceback is withheld.
		self.assertEqual(context["status"], "Failed")

	def test_clear_old_logs_deletes_attached_source_file(self):
		from frappe.utils import add_days, now_datetime

		from frappe.core.doctype.document_queue.document_queue import DocumentQueue

		queue_doc = self.make_queue()
		file_name = frappe.db.get_value("File", {"file_url": queue_doc.source_file}, "name")

		# Backdate past the retention window instead of using the default 30 days.
		frappe.db.set_value("Document Queue", queue_doc.name, "creation", add_days(now_datetime(), -31))

		DocumentQueue.clear_old_logs(days=30)

		self.assertFalse(frappe.db.exists("Document Queue", queue_doc.name))
		self.assertFalse(frappe.db.exists("File", file_name))

	def test_clear_old_logs_commits_after_each_batch(self):
		from frappe.utils import add_days, now_datetime

		from frappe.core.doctype.document_queue.document_queue import DocumentQueue

		queue_doc = self.make_queue()
		frappe.db.set_value("Document Queue", queue_doc.name, "creation", add_days(now_datetime(), -31))

		# A large backlog must not run as one long-held transaction; each batch should commit.
		with patch("frappe.db.commit", wraps=frappe.db.commit) as commit:
			DocumentQueue.clear_old_logs(days=30)

		commit.assert_called()

	def test_ready_for_review_count_requires_enabled_doctype(self):
		from frappe.core.doctype.document_queue.document_queue import get_ready_for_review_count

		queue_doc = self.make_queue()
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		self.assertEqual(get_ready_for_review_count("File"), 0)

		self.enable_upload_first_workflow("File")

		self.assertEqual(get_ready_for_review_count("File"), 1)

	# Owner scoping is not in get_permission_query_conditions() by design: the Desk User
	# DocPerm is if_owner, so db_query already ANDs `owner = user` onto the hook's
	# document_type filter. The two compose; the hook must not duplicate the owner clause.
	def test_ready_for_review_count_respects_owner_permissions(self):
		from frappe.core.doctype.document_queue.document_queue import get_ready_for_review_count

		user = self.make_desk_user()
		owned_queue_doc = self.make_queue()
		other_queue_doc = self.make_queue()
		self.enable_upload_first_workflow("File")

		owned_queue_doc.db_set(
			{"document_type": "File", "status": "Ready for Review", "owner": user.name}
		)
		other_queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		self.assertEqual(get_ready_for_review_count("File"), 2)

		with self.set_user(user.name):
			self.assertEqual(get_ready_for_review_count("File"), 1)

	def test_desk_user_can_link_document(self):
		from frappe.core.doctype.document_queue.document_queue import link_to_document

		user = self.make_desk_user()

		target_file = self.make_file()
		# Grant target_file write access to the user so they can link to it
		frappe.share.add(doctype="File", name=target_file.name, user=user.name, read=1, write=1)

		# Create a queue document owned by the desk user
		queue_doc = self.make_queue()
		queue_doc.db_set({
			"document_type": "File",
			"status": "Ready for Review",
			"owner": user.name
		})

		# The Desk User should be able to invoke link_to_document without PermissionError
		with self.set_user(user.name):
			result = link_to_document(queue_doc.name, "File", target_file.name)

		self.assertTrue(result.get("ok"))
		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Completed")
		self.assertEqual(queue_doc.created_document, target_file.name)
