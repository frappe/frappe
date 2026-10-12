# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from pathlib import Path

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, now
from frappe.utils.file_manager import get_file_path
from frappe.utils.task_queue import enqueue_task

PDF_EXTENSION = ".pdf"
IMAGE_EXTENSIONS = (".jpeg", ".jpg", ".png")
SUPPORTED_EXTENSIONS = (PDF_EXTENSION, *IMAGE_EXTENSIONS)

EXTRACTION_METHOD_PDF_TEXT_LAYER = "PDF Text Layer"
EXTRACTION_METHOD_PREVIEW_ONLY = "Preview Only"

PENDING_STATUSES = ("Queued", "Processing")
FINISHED_STATUSES = ("Completed", "Failed")

STALE_EXTRACTION_THRESHOLD = 6 * 60 * 60


class AttachmentQueue(Document):
	"""A file waiting for text extraction."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		document_type: DF.Link
		error_message: DF.SmallText | None
		extracted_text: DF.LongText | None
		extraction_method: DF.Data | None
		extraction_queued_on: DF.Datetime | None
		source_file: DF.Attach
		status: DF.Literal["Queued", "Processing", "Completed", "Failed"]
		task: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if not self.source_file:
			return

		self.validate_source_file_type()
		self.validate_source_file_access()

	def validate_source_file_type(self):
		if get_file_extension(self.source_file) not in SUPPORTED_EXTENSIONS:
			frappe.throw(
				_("Attach a PDF or an image. Other file types cannot be read."),
				title=_("Unsupported File"),
			)

	def validate_source_file_access(self):
		file_name = frappe.db.get_value("File", {"file_url": self.source_file}, "name")
		if not file_name:
			frappe.throw(
				_("{0} is not an uploaded file.").format(self.source_file),
				title=_("Unknown File"),
			)

		frappe.get_doc("File", file_name).check_permission("read")

	def after_insert(self):
		self.enqueue_extraction()

	def on_update(self):
		if not self.get_doc_before_save():
			return

		if not self.has_value_changed("source_file"):
			return

		# A queued job will use the updated file.
		if self.status == "Queued":
			return

		self.enqueue_extraction()

	def enqueue_extraction(self):
		task = enqueue_task(
			extract_attachment_text,
			task_name=_("Extract text from {0}").format(Path(self.source_file).name),
			ref_doctype=self.doctype,
			ref_docname=self.name,
			job_id=f"attachment-queue-extract::{self.name}",
			deduplicate=True,
			attachment_queue=self.name,
		)

		# Clear the previous result so it never sits next to a file it did not come from.
		self.db_set(
			{
				"status": "Queued",
				"task": task.name,
				"extraction_queued_on": now(),
				"extracted_text": None,
				"extraction_method": None,
				"error_message": None,
			}
		)

	def extract(self) -> tuple[str, str]:
		"""Return the extracted text and extraction method."""
		file_path = get_file_path(self.source_file)
		if not file_path:
			frappe.throw(_("Could not find {0}.").format(self.source_file))

		if get_file_extension(self.source_file) == PDF_EXTENSION:
			return extract_pdf_text(file_path), EXTRACTION_METHOD_PDF_TEXT_LAYER

		return "", EXTRACTION_METHOD_PREVIEW_ONLY

	@staticmethod
	def clear_old_logs(days: int = 30) -> None:
		cutoff = add_to_date(now(), days=-cint(days), as_datetime=True)
		rows = frappe.get_all(
			"Attachment Queue",
			filters={"modified": ("<", cutoff), "status": ("in", FINISHED_STATUSES)},
			pluck="name",
		)

		for name in rows:
			frappe.delete_doc("Attachment Queue", name, delete_permanently=True)


def extract_attachment_text(attachment_queue: str) -> None:
	# Updating modified prevents an older form from overwriting the result.
	queue_doc = frappe.get_doc("Attachment Queue", attachment_queue)
	queue_doc.db_set(
		{
			"status": "Processing",
			"extracted_text": None,
			"extraction_method": None,
			"error_message": None,
		}
	)

	try:
		extracted_text, extraction_method = queue_doc.extract()
	except Exception as exc:
		# Save the failure before the task wrapper rolls back.
		frappe.db.rollback()
		frappe.db.set_value(
			"Attachment Queue",
			attachment_queue,
			{"status": "Failed", "error_message": str(exc) or exc.__class__.__name__},
		)
		frappe.db.commit()
		raise

	queue_doc.db_set(
		{
			"status": "Completed",
			"extracted_text": extracted_text,
			"extraction_method": extraction_method,
		}
	)


def extract_pdf_text(file_path: str) -> str:
	from pypdf import PdfReader

	pages = [page.extract_text() or "" for page in PdfReader(file_path).pages]
	return "\n\n".join(page for page in pages if page.strip()).strip()


def get_file_extension(file_url: str) -> str:
	return Path(file_url.split("?", 1)[0]).suffix.lower()


def fail_stale_extractions() -> None:
	"""Mark extractions that have been stuck for too long as failed."""
	cutoff = add_to_date(now(), seconds=-STALE_EXTRACTION_THRESHOLD, as_datetime=True)
	stale = frappe.get_all(
		"Attachment Queue",
		filters={"status": ("in", PENDING_STATUSES), "extraction_queued_on": ("<", cutoff)},
		pluck="name",
	)

	if not stale:
		return

	frappe.db.set_value(
		"Attachment Queue",
		{"name": ("in", stale)},
		{"status": "Failed", "error_message": _("Text extraction did not finish.")},
	)
