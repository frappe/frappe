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


class TestAttachmentQueue(IntegrationTestCase):
	def make_file(self, file_name=None, content=None):
		file_name = file_name or f"document-{uuid4().hex}.pdf"
		content = content if content is not None else self.make_pdf_content()
		file_doc = save_file(file_name, content, None, None, is_private=1)
		self.addCleanup(lambda: frappe.delete_doc("File", file_doc.name, force=True, ignore_permissions=True))
		return file_doc

	def make_queue(self, file_name=None, content=None, auto_extract=False, document_type="File"):
		file_doc = self.make_file(file_name, content)
		queue_doc = frappe.get_doc(
			{"doctype": "Attachment Queue", "source_file": file_doc.file_url, "document_type": document_type}
		)
		if not auto_extract:
			queue_doc.flags.skip_auto_extraction = True
		queue_doc.insert()
		self.addCleanup(
			lambda: frappe.delete_doc("Attachment Queue", queue_doc.name, force=True, ignore_permissions=True)
		)
		return queue_doc

	def make_task_for(self, queue_doc, status, task_status):
		"""Put a queue row mid-flight behind a Background Task in a given state."""
		task = frappe.get_doc(
			{
				"doctype": "Background Task",
				"task_id": uuid4().hex,
				"job_id": f"attachment_queue_extract:{queue_doc.name}",
				"task_name": f"Extract document {queue_doc.name}",
				"method": (
					"frappe.core.doctype.attachment_queue.attachment_queue.extract_attachment_queue_record"
				),
				"status": task_status,
				"user": frappe.session.user,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.delete_doc("Background Task", task.name, force=True, ignore_permissions=True)
		)
		queue_doc.db_set({"status": status, "task": task.name})
		# make_queue leaves skip_auto_extraction on the doc it returns; enqueue_extraction_if_needed
		# checks that flag first, so the caller needs a doc without it.
		return frappe.get_doc("Attachment Queue", queue_doc.name)

	def make_desk_user(self):
		email = f"attachment-queue-user-{uuid4().hex}@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Attachment Queue",
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

	def test_creates_attachment_queue_record(self):
		queue_doc = self.make_queue()

		self.assertEqual(queue_doc.status, "Draft")
		self.assertTrue(queue_doc.source_file.endswith(".pdf"))

	def test_queues_extraction_when_attachment_queue_record_is_created(self):
		with patch(
			"frappe.core.doctype.attachment_queue.attachment_queue.enqueue_document_extraction"
		) as enqueue_document_extraction:
			queue_doc = self.make_queue(auto_extract=True)

		enqueue_document_extraction.assert_called_once_with(
			queue_doc.name, queue="default", enqueue_after_commit=True
		)

	def test_does_not_requeue_extraction_when_unrelated_field_changes(self):
		queue_doc = self.make_queue()
		reloaded = frappe.get_doc("Attachment Queue", queue_doc.name)

		with patch(
			"frappe.core.doctype.attachment_queue.attachment_queue.enqueue_document_extraction"
		) as enqueue_document_extraction:
			reloaded.document_type = "File"
			reloaded.save()

		enqueue_document_extraction.assert_not_called()

	def test_does_not_requeue_extraction_while_in_progress_or_completed(self):
		queue_doc = self.make_queue()
		alternate_files = [self.make_file(), self.make_file()]

		for i, status in enumerate(("Queued", "Processing", "Completed")):
			queue_doc.db_set("status", status, update_modified=False)
			reloaded = frappe.get_doc("Attachment Queue", queue_doc.name)

			with patch(
				"frappe.core.doctype.attachment_queue.attachment_queue.enqueue_document_extraction"
			) as enqueue_document_extraction:
				# Alternate source_file so has_value_changed is True, isolating the status guard.
				reloaded.source_file = alternate_files[i % 2].file_url
				reloaded.save()

			enqueue_document_extraction.assert_not_called()

	def test_cancelled_extraction_does_not_strand_the_queue_row(self):
		"""A cancelled task must leave the row recoverable, not mid-flight.

		Cancellation runs no callback on either path: the job is dropped before the worker
		sees it, or the work horse is killed mid-extraction. Nothing on this side gets to
		write, so the row keeps its status - and Queued/Processing are exactly the two
		statuses that then refuse to re-enqueue it.
		"""
		from frappe.core.doctype.attachment_queue.attachment_queue import REVIEWABLE_STATUSES

		for status in ("Queued", "Processing"):
			with self.subTest(status=status):
				queue_doc = self.make_task_for(self.make_queue(), status, "Cancelled")

				with patch(
					"frappe.core.doctype.attachment_queue.attachment_queue.enqueue_document_extraction"
				) as enqueue_document_extraction:
					queue_doc.enqueue_extraction_if_needed(force=True)

				# Failed, not a status of its own, and not still reading as active work. The
				# file is intact, so the intake goes back in front of a reviewer.
				queue_doc.reload()
				self.assertEqual(queue_doc.status, "Failed")
				self.assertIn(queue_doc.status, REVIEWABLE_STATUSES)
				self.assertIn("cancel", queue_doc.error_message.lower())

				# ... and the row no longer blocks its own retry.
				enqueue_document_extraction.assert_called_once()

	def test_live_extraction_task_still_blocks_re_enqueue(self):
		"""Only a cancelled task releases the guard.

		The Queued/Processing check is what stops a second save from extracting the same
		file twice. Recovery must not fire on a task that is merely still in flight.
		"""
		for status, task_status in (("Queued", "Queued"), ("Processing", "Running")):
			with self.subTest(status=status):
				queue_doc = self.make_task_for(self.make_queue(), status, task_status)

				with patch(
					"frappe.core.doctype.attachment_queue.attachment_queue.enqueue_document_extraction"
				) as enqueue_document_extraction:
					queue_doc.enqueue_extraction_if_needed(force=True)

				queue_doc.reload()
				self.assertEqual(queue_doc.status, status)
				enqueue_document_extraction.assert_not_called()

	def test_extracts_pdf_and_marks_ready_for_review(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import extract_attachment_queue_record

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
			"frappe.core.doctype.attachment_queue.attachment_queue._get_pdfplumber", return_value=pdfplumber
		):
			extract_attachment_queue_record(queue_doc.name)

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
		from frappe.core.doctype.attachment_queue.attachment_queue import extract_attachment_queue_record

		queue_doc = self.make_queue(
			file_name=f"document-{uuid4().hex}.txt",
			content=f"not a pdf {uuid4().hex}".encode(),
		)

		with self.assertRaises(Exception):
			extract_attachment_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Failed")
		self.assertIn("Only PDF and image extraction is supported", queue_doc.error_message)
		self.assertTrue(queue_doc.debug_output)

	def test_marks_failed_when_pdf_cannot_be_parsed(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import extract_attachment_queue_record

		queue_doc = self.make_queue()

		with patch(
			"frappe.core.doctype.attachment_queue.attachment_queue._get_pdfplumber",
			return_value=FakeCorruptPDFPlumber(),
		):
			with self.assertRaises(Exception):
				extract_attachment_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Failed")
		self.assertIn("corrupt pdf structure", queue_doc.error_message)
		self.assertIn("Traceback", queue_doc.debug_output)
		self.assertFalse(queue_doc.extracted_text)
		self.assertFalse(queue_doc.raw_extraction_json)

	def test_requeue_clears_stale_error_after_failed_extraction(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import extract_attachment_queue_record

		queue_doc = self.make_queue(
			file_name=f"document-{uuid4().hex}.txt",
			content=f"not a pdf {uuid4().hex}".encode(),
		)

		with self.assertRaises(Exception):
			extract_attachment_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Failed")
		self.assertTrue(queue_doc.error_message)

		# Retry must not let the prior failure linger next to the new result.
		queue_doc.mark_queued()
		queue_doc.reload()
		self.assertFalse(queue_doc.error_message)
		self.assertFalse(queue_doc.debug_output)

	def test_accepts_image_without_extracting_text(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import extract_attachment_queue_record

		# The framework ships no image text extraction. An image is still a valid queue
		# input: it reaches review with an empty extraction, for the reviewer to read off
		# the preview pane and key in by hand.
		queue_doc = self.make_queue(
			file_name=f"document-{uuid4().hex}.png",
			content=b"fake image content",
		)

		extract_attachment_queue_record(queue_doc.name)

		queue_doc.reload()
		raw = frappe.parse_json(queue_doc.raw_extraction_json)

		self.assertEqual(queue_doc.status, "Ready for Review")
		self.assertEqual(queue_doc.extraction_method, "Preview Only")
		self.assertFalse(queue_doc.extracted_text)
		self.assertEqual(raw["pages"], [])
		self.assertFalse(queue_doc.error_message)

	def test_completes_when_pdf_has_no_embedded_text_layer(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import extract_attachment_queue_record

		# A scanned PDF yields nothing from pdfplumber. That is an empty extraction, not a
		# failure — the row still reaches review so the file can be keyed in from the preview.
		queue_doc = self.make_queue()
		pdfplumber = FakePDFPlumber([FakePDFPage(text="", layout_text="", words=[], tables=[])])

		with patch(
			"frappe.core.doctype.attachment_queue.attachment_queue._get_pdfplumber", return_value=pdfplumber
		):
			extract_attachment_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Ready for Review")
		self.assertEqual(queue_doc.extraction_method, "pdfplumber")
		self.assertFalse(queue_doc.extracted_text)
		self.assertFalse(queue_doc.error_message)

	def test_desk_user_cannot_create_queue_row_directly(self):
		# Queue rows are framework-owned, like Email Queue: they are created for the user by
		# create_upload_first_queue(), never authored from a form.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1, create=1)

		with self.set_user(user.name):
			file_doc = self.make_file()
			queue_doc = frappe.get_doc(
				{
					"doctype": "Attachment Queue",
					"source_file": file_doc.file_url,
					"document_type": target_doctype,
				}
			)
			queue_doc.flags.skip_auto_extraction = True

			with self.assertRaises(frappe.PermissionError):
				queue_doc.insert()

	def test_upload_first_queue_requires_create_on_target_doctype(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import create_upload_first_queue

		# The row is inserted with ignore_permissions, so create on the target DocType is
		# the check standing in for it.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1)

		with self.set_user(user.name):
			file_doc = self.make_file()

			with self.assertRaises(frappe.PermissionError):
				create_upload_first_queue(file_doc.name, target_doctype)

	def test_desk_user_can_create_upload_first_queue_for_permitted_target(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import create_upload_first_queue

		# Counterpart to the test above: create on the target DocType is what unlocks it.
		user = self.make_desk_user()
		target_doctype = self.make_target_doctype(read=1, create=1)

		with self.set_user(user.name):
			file_doc = self.make_file()
			context = create_upload_first_queue(file_doc.name, target_doctype)

		self.addCleanup(
			lambda: frappe.delete_doc(
				"Attachment Queue", context["queue_name"], force=True, ignore_permissions=True
			)
		)
		queue_doc = frappe.get_doc("Attachment Queue", context["queue_name"])
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
			self.assertTrue(frappe.has_permission("Attachment Queue", "read", doc=queue_doc))

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
		from frappe.core.doctype.attachment_queue.attachment_queue import create_upload_first_queue

		self.enable_upload_first_workflow("File")
		file_doc = self.make_file()
		context = create_upload_first_queue(file_doc.name, "File")

		queue_doc = frappe.get_doc("Attachment Queue", context["queue_name"])
		self.addCleanup(
			lambda: frappe.delete_doc("Attachment Queue", queue_doc.name, force=True, ignore_permissions=True)
		)

		file_doc.reload()
		self.assertEqual(queue_doc.document_type, "File")
		self.assertEqual(queue_doc.status, "Queued")
		self.assertTrue(queue_doc.task)
		self.assertEqual(context["document_type"], "File")
		self.assertEqual(context["source_file"], file_doc.file_url)
		self.assertEqual(context["status"], "Queued")
		self.assertEqual(file_doc.attached_to_doctype, "Attachment Queue")
		self.assertEqual(file_doc.attached_to_name, queue_doc.name)

	def test_create_queue_without_file_write_permission(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import create_upload_first_queue

		self.enable_upload_first_workflow("File")

		# Owned by Administrator, so the user below only gets what the share grants.
		file_doc = self.make_file()
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"attachment-queue-reader-{uuid4().hex}@example.com",
				"first_name": "Attachment Queue Reader",
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
		from frappe.core.doctype.attachment_queue.attachment_queue import get_document_review_context

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
		from frappe.core.doctype.attachment_queue.attachment_queue import get_document_review_context

		# The review panel shows this to whoever is reviewing a Failed row, so it has to
		# reach them regardless of developer mode.
		queue_doc = self.make_queue()
		queue_doc.db_set({"status": "Failed", "error_message": "Only PDF and image extraction"})

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			context = get_document_review_context(queue_doc.name)

		self.assertEqual(context["status"], "Failed")
		self.assertIn("Only PDF and image extraction", context["error_message"])

	def test_link_to_document_marks_completed(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

		queue_doc = self.make_queue()
		target_file = self.make_file(file_name=f"target-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		result = link_to_document(queue_doc.name, "File", target_file.name)

		queue_doc.reload()
		self.assertTrue(result["ok"])
		self.assertTrue(result["attached"])
		self.assertEqual(queue_doc.status, "Completed")
		self.assertEqual(queue_doc.document_type, "File")
		self.assertEqual(queue_doc.created_document, target_file.name)

		source_file = frappe.get_doc("File", frappe.db.get_value("File", {"file_url": queue_doc.source_file}))
		self.assertEqual(source_file.attached_to_doctype, "File")
		self.assertEqual(source_file.attached_to_name, target_file.name)

	def test_link_to_document_reports_when_the_source_file_is_gone(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

		# A row whose File has been deleted since it was created has nothing to hand over.
		# Refusing the link would wedge the reviewer — their document is already saved and
		# the file cannot be brought back — so the row moves on, and the one thing that must
		# not happen is reporting an attachment that did not happen.
		queue_doc = self.make_queue()
		target_file = self.make_file(file_name=f"target-{uuid4().hex}.pdf")
		queue_doc.db_set(
			{
				"document_type": "File",
				"status": "Ready for Review",
				"source_file": f"/private/files/gone-{uuid4().hex}.pdf",
			}
		)

		result = link_to_document(queue_doc.name, "File", target_file.name)

		self.assertTrue(result["ok"])
		self.assertFalse(result["attached"])

		# The row is still claimed: there is nothing left to review, and leaving it open
		# would keep offering a review for a file that no longer exists.
		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Completed")
		self.assertEqual(queue_doc.created_document, target_file.name)

		self.assertFalse(
			frappe.db.exists("File", {"attached_to_doctype": "File", "attached_to_name": target_file.name})
		)

		messages = " ".join(str(message) for message in frappe.get_message_log())
		self.assertIn(queue_doc.name, messages)

	def test_link_to_document_rejects_mismatched_document_type(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

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
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

		queue_doc = self.make_queue()
		first_target = self.make_file(file_name=f"first-{uuid4().hex}.pdf")
		second_target = self.make_file(file_name=f"second-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		link_to_document(queue_doc.name, "File", first_target.name)

		# Re-linking moves the row on but not the source file, which is already attached to
		# the first document — the row and the file would end up pointing at different docs.
		# created_document is what refuses it, not the row's status: the status guard would
		# also refuse a first link taken while extraction was still running.
		with self.assertRaises(frappe.ValidationError):
			link_to_document(queue_doc.name, "File", second_target.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.created_document, first_target.name)

	def test_link_to_document_rejects_a_claim_taken_before_the_winner_committed(self):
		"""Two concurrent links must not both pass the created_document check.

		Both requests snapshot the row before either writes, so both snapshots say
		unclaimed. This is the loser: its snapshot is that stale read, while the winner's
		claim is already in the database. Only a locked read of the live row refuses it -
		checking the snapshot would overwrite created_document and leave the row pointing
		at one document while the source file sat on the other.
		"""
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

		queue_doc = self.make_queue()
		winner = self.make_file(file_name=f"winner-{uuid4().hex}.pdf")
		loser = self.make_file(file_name=f"loser-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		link_to_document(queue_doc.name, "File", winner.name)

		real_get_doc = frappe.get_doc

		def stale_snapshot(*args, **kwargs):
			doc = real_get_doc(*args, **kwargs)
			if doc.doctype == "Attachment Queue" and doc.name == queue_doc.name:
				# The read the loser took before the winner's claim landed.
				doc.created_document = None
			return doc

		with patch.object(frappe, "get_doc", side_effect=stale_snapshot):
			with self.assertRaises(frappe.ValidationError):
				link_to_document(queue_doc.name, "File", loser.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.created_document, winner.name)

		# The winner keeps the source file: the refused claim moved nothing.
		source_file = frappe.get_doc("File", frappe.db.get_value("File", {"file_url": queue_doc.source_file}))
		self.assertEqual(source_file.attached_to_doctype, "File")
		self.assertEqual(source_file.attached_to_name, winner.name)

	def test_upload_first_save_while_queued_puts_the_file_on_the_document(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import (
			create_upload_first_queue,
			link_to_document,
		)
		from frappe.desk.form.load import get_attachments

		# The production entry point, end to end: the upload-first banner creates the row,
		# extraction is still Queued, and the reviewer saves before it finishes. The other
		# tests build their queue row by hand; this one goes through the flow a reviewer
		# actually drives, and asserts the thing they actually see — the source file in the
		# target document's Attachments section, which is what get_attachments feeds.
		target_doctype = self.make_target_doctype(read=1, write=1, create=1)
		file_doc = self.make_file()

		context = create_upload_first_queue(file_doc.name, target_doctype)
		self.addCleanup(
			lambda: frappe.delete_doc(
				"Attachment Queue", context["queue_name"], force=True, ignore_permissions=True
			)
		)
		self.assertEqual(context["status"], "Queued")

		target_doc = frappe.new_doc(target_doctype).insert(ignore_permissions=True)
		result = link_to_document(context["queue_name"], target_doctype, target_doc.name)

		self.assertTrue(result["attached"])
		# The save claims the row without ending it: extraction still owns the status.
		self.assertEqual(result["status"], "Queued")

		attachments = get_attachments(target_doctype, target_doc.name)
		self.assertEqual([row.file_url for row in attachments], [file_doc.file_url])

	def test_link_to_document_claims_a_row_that_is_still_extracting(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

		# The upload-first flow knows the target DocType from the moment the file is
		# uploaded, so a reviewer can save the document before extraction finishes. That
		# save has to put the source file on the document it produced; refusing it left the
		# document with an empty Attachments section and the row back in the review modal.
		queue_doc = self.make_queue()
		target_file = self.make_file(file_name=f"target-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Processing"})

		result = link_to_document(queue_doc.name, "File", target_file.name)

		queue_doc.reload()
		self.assertTrue(result["ok"])
		self.assertEqual(queue_doc.created_document, target_file.name)
		# Extraction owns the status until it ends. Claiming the row does not end it.
		self.assertEqual(queue_doc.status, "Processing")

		source_file = frappe.get_doc("File", frappe.db.get_value("File", {"file_url": queue_doc.source_file}))
		self.assertEqual(source_file.attached_to_doctype, "File")
		self.assertEqual(source_file.attached_to_name, target_file.name)

	def test_link_to_document_rejects_a_second_link_while_still_extracting(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

		# The guard moved from the status to created_document; this is what proves it moved
		# rather than went away. A mid-extraction row is linkable exactly once.
		queue_doc = self.make_queue()
		first_target = self.make_file(file_name=f"first-{uuid4().hex}.pdf")
		second_target = self.make_file(file_name=f"second-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Queued"})

		link_to_document(queue_doc.name, "File", first_target.name)

		with self.assertRaises(frappe.ValidationError):
			link_to_document(queue_doc.name, "File", second_target.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.created_document, first_target.name)

	def test_extraction_completing_after_a_link_does_not_reopen_the_row(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import (
			extract_attachment_queue_record,
			link_to_document,
		)

		# The worker fetches the row before the slow part and writes its terminal status
		# after it, so a link taken in between is invisible to it. Writing "Ready for
		# Review" unconditionally would put a row that has already produced its document
		# back into the review modal — the symptom this whole change exists to fix.
		queue_doc = self.make_queue()
		target_file = self.make_file(file_name=f"target-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Processing"})
		link_to_document(queue_doc.name, "File", target_file.name)

		pdfplumber = FakePDFPlumber([FakePDFPage(text="Invoice", layout_text="Invoice")])
		with patch(
			"frappe.core.doctype.attachment_queue.attachment_queue._get_pdfplumber", return_value=pdfplumber
		):
			extract_attachment_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Completed")
		self.assertEqual(queue_doc.created_document, target_file.name)
		# The extraction still lands in full — the reviewer is watching for it.
		self.assertIn("Invoice", queue_doc.extracted_text)
		self.assertEqual(queue_doc.extraction_method, "pdfplumber")
		self.assertTrue(queue_doc.extraction_completed_on)

	def test_extraction_failing_after_a_link_does_not_reopen_the_row(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import (
			extract_attachment_queue_record,
			link_to_document,
		)

		# Failed is a reviewable status, so a failure has to be held to the same rule:
		# the document exists and owns the source file, and there is no review left to
		# offer. The reason is still recorded on the row.
		queue_doc = self.make_queue()
		target_file = self.make_file(file_name=f"target-{uuid4().hex}.pdf")
		queue_doc.db_set({"document_type": "File", "status": "Processing"})
		link_to_document(queue_doc.name, "File", target_file.name)

		with patch(
			"frappe.core.doctype.attachment_queue.attachment_queue._get_pdfplumber",
			return_value=FakeCorruptPDFPlumber(),
		):
			with self.assertRaises(Exception):
				extract_attachment_queue_record(queue_doc.name)

		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Completed")
		self.assertEqual(queue_doc.created_document, target_file.name)
		self.assertIn("corrupt pdf structure", queue_doc.error_message)

	def test_ready_for_review_count_excludes_a_row_linked_while_extracting(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import (
			extract_attachment_queue_record,
			get_ready_for_review_count,
			link_to_document,
		)

		queue_doc = self.make_queue()
		target_file = self.make_file(file_name=f"target-{uuid4().hex}.pdf")
		self.enable_upload_first_workflow("File")
		queue_doc.db_set({"document_type": "File", "status": "Processing"})

		link_to_document(queue_doc.name, "File", target_file.name)

		# Before extraction settles the row is still Processing, which the count never
		# included; after it settles it is Completed, which is the half that used to break.
		self.assertEqual(get_ready_for_review_count("File"), 0)

		pdfplumber = FakePDFPlumber([FakePDFPage(text="Invoice", layout_text="Invoice")])
		with patch(
			"frappe.core.doctype.attachment_queue.attachment_queue._get_pdfplumber", return_value=pdfplumber
		):
			extract_attachment_queue_record(queue_doc.name)

		self.assertEqual(get_ready_for_review_count("File"), 0)

	def test_target_document_can_be_deleted_while_queue_row_survives(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

		# A queue row records work that was done; it is not a business reference to the
		# document it produced. Registering the DocType in ignore_links_on_delete is what
		# keeps created_document out of the link check, the way Email Queue and
		# Integration Request keep theirs out.
		# read=1 only because a DocPerm row with no rights at all fails DocType validation;
		# this test runs as Administrator and does not exercise Desk User permissions.
		target_doctype = self.make_target_doctype(read=1)
		target_doc = frappe.new_doc(target_doctype).insert(ignore_permissions=True)
		queue_doc = self.make_queue(document_type=target_doctype)
		queue_doc.db_set("status", "Ready for Review")

		link_to_document(queue_doc.name, target_doctype, target_doc.name)

		# No force: that flag skips the link check this test exists to cover.
		frappe.delete_doc(target_doctype, target_doc.name)

		self.assertFalse(frappe.db.exists(target_doctype, target_doc.name))

		# The row stays as it was. document_type in particular is load-bearing: has_permission
		# and get_permission_query_conditions both read it.
		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Completed")
		self.assertEqual(queue_doc.document_type, target_doctype)
		self.assertEqual(queue_doc.created_document, target_doc.name)

	def test_review_context_withholds_debug_output_from_non_privileged_owner(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import get_document_review_context

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
		from frappe.core.doctype.attachment_queue.attachment_queue import AttachmentQueue
		from frappe.utils import add_days, now_datetime

		queue_doc = self.make_queue()
		file_name = frappe.db.get_value("File", {"file_url": queue_doc.source_file}, "name")

		# Completed because that is the only status cleanup touches. The file is still on the
		# row here, which is what the assertion needs: delete_doc has to take it along rather
		# than orphan it on disk.
		queue_doc.db_set("status", "Completed")

		# Backdate past the retention window instead of using the default 30 days.
		frappe.db.set_value("Attachment Queue", queue_doc.name, "creation", add_days(now_datetime(), -31))

		AttachmentQueue.clear_old_logs(days=30)

		self.assertFalse(frappe.db.exists("Attachment Queue", queue_doc.name))
		self.assertFalse(frappe.db.exists("File", file_name))

	def test_clear_old_logs_commits_after_each_batch(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import AttachmentQueue
		from frappe.utils import add_days, now_datetime

		queue_doc = self.make_queue()
		queue_doc.db_set("status", "Completed")
		frappe.db.set_value("Attachment Queue", queue_doc.name, "creation", add_days(now_datetime(), -31))

		# A large backlog must not run as one long-held transaction; each batch should commit.
		with patch("frappe.db.commit", wraps=frappe.db.commit) as commit:
			AttachmentQueue.clear_old_logs(days=30)

		commit.assert_called()

	def test_clear_old_logs_keeps_intake_that_is_not_finished(self):
		"""Cleanup is a log purge, not an intake purge.

		A row is disposable only once it has produced its document. Anything still
		extracting, or still waiting for a reviewer, owns its source file - that upload is
		the only copy of it, and delete_doc takes the File along with the row. Age alone
		must not decide this.
		"""
		from frappe.core.doctype.attachment_queue.attachment_queue import (
			REVIEWABLE_STATUSES,
			AttachmentQueue,
		)
		from frappe.utils import add_days, now_datetime

		def backdated_queue(status):
			queue_doc = self.make_queue()
			queue_doc.db_set("status", status)
			frappe.db.set_value("Attachment Queue", queue_doc.name, "creation", add_days(now_datetime(), -31))
			file_name = frappe.db.get_value("File", {"file_url": queue_doc.source_file}, "name")
			return queue_doc.name, file_name

		# Draft and Queued are waiting for a worker, Processing is mid-extraction, and
		# REVIEWABLE_STATUSES are waiting for a reviewer. None of them has handed its file over.
		retained = {
			status: backdated_queue(status)
			for status in ("Draft", "Queued", "Processing", *REVIEWABLE_STATUSES)
		}
		finished_name, finished_file = backdated_queue("Completed")

		AttachmentQueue.clear_old_logs(days=30)

		for status, (name, file_name) in retained.items():
			self.assertTrue(frappe.db.exists("Attachment Queue", name), f"{status} row was deleted")
			self.assertTrue(frappe.db.exists("File", file_name), f"{status} source file was deleted")

		# The row that produced its document is finished, and is still purged.
		self.assertFalse(frappe.db.exists("Attachment Queue", finished_name))
		self.assertFalse(frappe.db.exists("File", finished_file))

	def test_ready_for_review_count_requires_enabled_doctype(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import get_ready_for_review_count

		queue_doc = self.make_queue()
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		self.assertEqual(get_ready_for_review_count("File"), 0)

		self.enable_upload_first_workflow("File")

		self.assertEqual(get_ready_for_review_count("File"), 1)

	# Owner scoping is not in get_permission_query_conditions() by design: the Desk User
	# DocPerm is if_owner, so db_query already ANDs `owner = user` onto the hook's
	# document_type filter. The two compose; the hook must not duplicate the owner clause.
	def test_ready_for_review_count_respects_owner_permissions(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import get_ready_for_review_count

		user = self.make_desk_user()
		owned_queue_doc = self.make_queue()
		other_queue_doc = self.make_queue()
		self.enable_upload_first_workflow("File")

		owned_queue_doc.db_set({"document_type": "File", "status": "Ready for Review", "owner": user.name})
		other_queue_doc.db_set({"document_type": "File", "status": "Ready for Review"})

		self.assertEqual(get_ready_for_review_count("File"), 2)

		with self.set_user(user.name):
			self.assertEqual(get_ready_for_review_count("File"), 1)

	def test_queue_list_excludes_rows_for_unreadable_doctypes(self):
		"""get_permission_query_conditions scopes the list to readable target DocTypes.

		A queue row exists only to feed a document, so it is exactly as reachable as the
		DocType it targets. Both rows here are owned by the same user, so the if_owner
		DocPerm cannot account for the difference - the target DocType is the only thing
		separating them.
		"""
		user = self.make_desk_user()
		readable = self.make_target_doctype(read=1)
		# create without read: a valid DocPerm row (DocType validation rejects an empty one)
		# that still leaves the DocType outside get_doctypes_with_read.
		unreadable = self.make_target_doctype(create=1)

		visible = self.make_queue(document_type=readable)
		hidden = self.make_queue(document_type=unreadable)
		visible.db_set("owner", user.name)
		hidden.db_set("owner", user.name)

		with self.set_user(user.name):
			# get_list, not get_all: get_all passes ignore_permissions and would skip the hook.
			names = frappe.get_list("Attachment Queue", pluck="name")

		self.assertIn(visible.name, names)
		self.assertNotIn(hidden.name, names)

	def test_desk_user_can_link_document(self):
		from frappe.core.doctype.attachment_queue.attachment_queue import link_to_document

		user = self.make_desk_user()

		target_file = self.make_file()
		# Grant target_file write access to the user so they can link to it
		frappe.share.add(doctype="File", name=target_file.name, user=user.name, read=1, write=1)

		# Create a queue document owned by the desk user
		queue_doc = self.make_queue()
		queue_doc.db_set({"document_type": "File", "status": "Ready for Review", "owner": user.name})

		# The Desk User should be able to invoke link_to_document without PermissionError
		with self.set_user(user.name):
			result = link_to_document(queue_doc.name, "File", target_file.name)

		self.assertTrue(result.get("ok"))
		queue_doc.reload()
		self.assertEqual(queue_doc.status, "Completed")
		self.assertEqual(queue_doc.created_document, target_file.name)
