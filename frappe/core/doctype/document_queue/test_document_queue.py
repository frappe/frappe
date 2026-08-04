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

	def make_queue(self, file_name=None, content=None, auto_extract=False):
		file_doc = self.make_file(file_name, content)
		queue_doc = frappe.get_doc({"doctype": "Document Queue", "source_file": file_doc.file_url})
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

	def test_read_only_owner_cannot_enqueue_or_set_document_type(self):
		user = self.make_desk_user()
		self.enable_upload_first_workflow("File")

		with self.set_user(user.name):
			queue_doc = self.make_queue()

			with patch.object(queue_doc, "enqueue_extraction") as enqueue_extraction:
				with self.assertRaises(frappe.PermissionError):
					queue_doc.extract_in_background()

			with self.assertRaises(frappe.PermissionError):
				queue_doc.set_document_type("File")

		enqueue_extraction.assert_not_called()

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
		
		# Create file as Administrator (current session)
		file_doc = self.make_file()

		# Create a standard user with read-only access to File
		user = frappe.get_doc({
			"doctype": "User",
			"email": "test_read_only_queue@example.com",
			"first_name": "Test",
			"roles": [{"role": "All"}],
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)

		# Explicitly share the file with the User, granting 'read' but not 'write'
		frappe.share.add(
			doctype="File",
			name=file_doc.name,
			user=user.name,
			read=1,
			write=0
		)

		frappe.set_user(user.name)

		# Attempt to create queue without write permission
		with self.assertRaises(frappe.PermissionError):
			create_upload_first_queue(file_doc.name, "File")

		frappe.set_user("Administrator")

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

		context = get_document_review_context(queue_doc.name)

		self.assertEqual(context["queue_name"], queue_doc.name)
		self.assertEqual(context["document_type"], "File")
		self.assertTrue(context["source_file_url"].startswith(queue_doc.source_file))
		self.assertIn("fid=", context["source_file_url"])
		self.assertEqual(context["extracted_text"], "Layout text")
		self.assertEqual(context["raw_extraction_json"]["pages"][0]["page_number"], 1)

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

	def test_ready_for_review_count_requires_enabled_doctype(self):
		from frappe.core.doctype.document_queue.document_queue import get_ready_for_review_count

		queue_doc = self.make_queue()
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		self.assertEqual(get_ready_for_review_count("File"), 0)

		self.enable_upload_first_workflow("File")

		self.assertEqual(get_ready_for_review_count("File"), 1)

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
