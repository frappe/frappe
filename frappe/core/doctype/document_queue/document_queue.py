# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now
from frappe.utils.file_manager import get_file_path
from frappe.utils.task_queue import enqueue_task


class UnsupportedExtractionFile(frappe.ValidationError):
	pass


class DocumentQueue(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		created_document: DF.DynamicLink | None
		debug_output: DF.LongText | None
		document_type: DF.Link | None
		error_message: DF.LongText | None
		extracted_text: DF.LongText | None
		extraction_completed_on: DF.Datetime | None
		extraction_method: DF.Data | None
		extraction_started_on: DF.Datetime | None
		raw_extraction_json: DF.JSON | None
		source_file: DF.Attach
		status: DF.Literal["Draft", "Queued", "Processing", "Ready for Review", "Completed", "Failed"]
		task: DF.Link | None
	# end: auto-generated types

	def before_insert(self):
		if not self.status:
			self.status = "Draft"

	def validate(self):
		if self.source_file and not (_is_pdf(self.source_file) or _is_image(self.source_file)):
			self.extraction_method = self.extraction_method or "Unsupported"

	def enqueue_extraction(self, *, queue: str = "default", enqueue_after_commit: bool = True) -> "Document":
		return enqueue_document_extraction(self.name, queue=queue, enqueue_after_commit=enqueue_after_commit)

	def extract(self) -> dict[str, Any]:
		return extract_document_queue_record(self.name)

	def mark_queued(self, task_name: str | None = None):
		values = {
			"status": "Queued",
			"extraction_started_on": None,
			"extraction_completed_on": None,
			"extracted_text": None,
			"raw_extraction_json": None,
			"error_message": None,
			"debug_output": None,
		}
		if task_name:
			values["task"] = task_name
		self.db_set(values, update_modified=False)

	def mark_processing(self):
		self.db_set(
			{
				"status": "Processing",
				"extraction_started_on": now(),
				"extraction_completed_on": None,
				"error_message": None,
				"debug_output": None,
			},
			update_modified=False,
		)

	def mark_completed(self, result: dict[str, Any]):
		self.db_set(
			{
				"status": "Ready for Review",
				"extraction_method": result.get("extraction_method"),
				"extraction_completed_on": now(),
				"extracted_text": result.get("extracted_text"),
				"raw_extraction_json": frappe.as_json(result.get("raw_extraction_json")),
				"debug_output": "\n".join(result.get("debug_output") or []),
				"error_message": None,
			},
			update_modified=False,
		)

	def mark_failed(self, error_message: str, debug_output: str | None = None):
		self.db_set(
			{
				"status": "Failed",
				"extraction_completed_on": now(),
				"error_message": error_message,
				"debug_output": debug_output,
			},
			update_modified=False,
		)

	def mark_review_completed(self, document_type: str, document_name: str):
		self.db_set(
			{
				"status": "Completed",
				"document_type": document_type,
				"created_document": document_name,
			},
			update_modified=False,
		)

	@frappe.whitelist()
	def extract_in_background(self):
		task = self.enqueue_extraction()
		frappe.msgprint(
			_("Queued extraction for {0}.").format(frappe.bold(self.name)),
			indicator="green",
			alert=True,
		)
		return task.name

	@frappe.whitelist()
	def set_document_type(self, document_type: str):
		validate_upload_first_workflow_doctype(document_type)

		self.db_set("document_type", document_type, update_modified=True)
		self.document_type = document_type
		return self.get_document_review_context()

	@frappe.whitelist()
	def get_document_review_context(self):
		return get_document_review_context(self.name)

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Document Queue")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


def enqueue_document_extraction(
	document_queue: str,
	*,
	queue: str = "default",
	enqueue_after_commit: bool = True,
) -> "Document":
	queue_doc = frappe.get_doc("Document Queue", document_queue)

	task = enqueue_task(
		_extract_document_queue_record,
		task_name=_("Extract document {0}").format(queue_doc.name),
		queue=queue,
		ref_doctype="Document Queue",
		ref_docname=queue_doc.name,
		job_id=f"document_queue_extract:{queue_doc.name}",
		deduplicate=True,
		enqueue_after_commit=enqueue_after_commit,
		document_queue=queue_doc.name,
	)

	queue_doc.mark_queued(task.name)
	return task


def extract_document_queue_record(document_queue: str) -> dict[str, Any]:
	queue_doc = frappe.get_doc("Document Queue", document_queue)
	queue_doc.mark_processing()
	frappe.db.commit()  # nosemgrep: Persist Processing before long-running extraction.

	try:
		file_path = get_file_path(queue_doc.source_file)
		result = extract_file(file_path)
		queue_doc.mark_completed(result)
		return result
	except Exception as exc:
		frappe.db.rollback()
		error_message = str(exc) or exc.__class__.__name__
		queue_doc = frappe.get_doc("Document Queue", document_queue)
		queue_doc.mark_failed(error_message, frappe.get_traceback(with_context=True))
		frappe.db.commit()  # nosemgrep: Preserve Failed status before re-raising.
		raise


def _extract_document_queue_record(document_queue: str) -> dict[str, Any]:
	return extract_document_queue_record(document_queue)


@frappe.whitelist()
def get_review_context(document_queue: str) -> dict[str, Any]:
	return get_document_review_context(document_queue)


@frappe.whitelist()
def is_upload_first_workflow_enabled(document_type: str) -> bool:
	return is_upload_first_workflow_doctype(document_type)


@frappe.whitelist()
def get_ready_for_review_count(document_type: str) -> int:
	if not is_upload_first_workflow_doctype(document_type):
		return 0

	return frappe.db.count(
		"Document Queue",
		{
			"document_type": document_type,
			"status": "Ready for Review",
		},
	)


@frappe.whitelist()
def create_upload_first_queue(file_name: str, document_type: str) -> dict[str, Any]:
	validate_upload_first_workflow_doctype(document_type)

	file_doc = frappe.get_doc("File", file_name)
	file_doc.check_permission("read")

	queue_doc = frappe.get_doc(
		{
			"doctype": "Document Queue",
			"source_file": file_doc.file_url,
			"document_type": document_type,
		}
	).insert()

	file_doc.db_set(
		{
			"attached_to_doctype": queue_doc.doctype,
			"attached_to_name": queue_doc.name,
			"attached_to_field": "source_file",
		},
		update_modified=False,
	)

	try:
		extract_document_queue_record(queue_doc.name)
	except Exception:
		pass

	return get_document_review_context(queue_doc.name)


@frappe.whitelist()
def get_document_review_context(document_queue: str) -> dict[str, Any]:
	queue_doc = frappe.get_doc("Document Queue", document_queue)
	queue_doc.check_permission("read")

	return {
		"queue_name": queue_doc.name,
		"status": queue_doc.status,
		"document_type": queue_doc.document_type,
		"created_document": queue_doc.created_document,
		"source_file": queue_doc.source_file,
		"source_file_url": _get_source_file_preview_url(queue_doc),
		"extracted_text": queue_doc.extracted_text or "",
		"raw_extraction_json": _parse_json(queue_doc.raw_extraction_json),
		"debug_output": queue_doc.debug_output or "",
	}


@frappe.whitelist()
def link_to_document(document_queue: str, document_type: str, document_name: str) -> dict[str, Any]:
	queue_doc = frappe.get_doc("Document Queue", document_queue)
	queue_doc.check_permission("write")

	if not frappe.db.exists(document_type, document_name):
		frappe.throw(
			_("Document {0} {1} does not exist.").format(
				frappe.bold(document_type), frappe.bold(document_name)
			)
		)

	target_doc = frappe.get_doc(document_type, document_name)
	target_doc.check_permission("write")
	queue_doc.mark_review_completed(target_doc.doctype, target_doc.name)
	attach_source_file_to_document(queue_doc, target_doc)

	return {
		"ok": True,
		"status": queue_doc.status,
		"document_type": queue_doc.document_type,
		"created_document": queue_doc.created_document,
	}


def attach_source_file_to_document(queue_doc: DocumentQueue, target_doc: Document):
	file_doc_name = frappe.db.get_value(
		"File",
		{
			"file_url": queue_doc.source_file,
			"attached_to_doctype": queue_doc.doctype,
			"attached_to_name": queue_doc.name,
		},
		"name",
	)
	if not file_doc_name:
		return

	file_doc = frappe.get_doc("File", file_doc_name)
	file_doc.db_set(
		{
			"attached_to_doctype": target_doc.doctype,
			"attached_to_name": target_doc.name,
			"attached_to_field": None,
		},
		update_modified=False,
	)


def validate_upload_first_workflow_doctype(document_type: str):
	if not frappe.db.exists("DocType", document_type):
		frappe.throw(_("DocType {0} does not exist.").format(frappe.bold(document_type)))

	if not is_upload_first_workflow_doctype(document_type):
		frappe.throw(
			_("{0} does not have Upload First Workflow enabled.").format(frappe.bold(document_type)),
			frappe.PermissionError,
		)


def is_upload_first_workflow_doctype(document_type: str) -> bool:
	if not document_type:
		return False

	values = frappe.db.get_value(
		"DocType",
		document_type,
		["enable_upload_first_workflow", "istable"],
		as_dict=True,
	)
	return bool(values and cint(values.enable_upload_first_workflow) and not cint(values.istable))


def extract_file(file_path: str) -> dict[str, Any]:
	if _is_image(file_path):
		return extract_image(file_path)

	if _is_pdf(file_path):
		return extract_pdf(file_path)

	raise UnsupportedExtractionFile(_("Only PDF and image extraction is supported for Document Queue"))


def extract_image(file_path: str) -> dict[str, Any]:
	text, words, debug_output = extract_image_text_with_tesseract(file_path)
	if not text:
		raise UnsupportedExtractionFile(_("Tesseract is required to extract text from images"))

	return {
		"extraction_method": "tesseract",
		"extracted_text": text,
		"raw_extraction_json": {
			"file": Path(file_path).name,
			"extraction_method": "tesseract",
			"pages": [
				{
					"page_number": 1,
					"text": text,
					"words": words,
					"tables": [],
				}
			],
		},
		"debug_output": debug_output,
	}


def extract_pdf(file_path: str) -> dict[str, Any]:
	pdfplumber = _get_pdfplumber()
	pages = []
	text_parts = []
	layout_text_parts = []
	debug_output = []

	with pdfplumber.open(file_path) as pdf:
		for page_number, page in enumerate(pdf.pages, start=1):
			text = page.extract_text() or ""
			layout_text = page.extract_text(layout=True) or ""
			words = page.extract_words(x_tolerance=1, y_tolerance=3) or []
			tables = page.extract_tables() or []

			text_parts.append(text)
			layout_text_parts.append(layout_text)
			pages.append(
				{
					"page_number": page_number,
					"width": page.width,
					"height": page.height,
					"text": text,
					"layout_text": layout_text,
					"words": _json_safe(words),
					"tables": _json_safe(tables),
				}
			)

	extracted_text = "\n\n".join(part for part in text_parts if part).strip()
	extracted_layout_text = "\n\n".join(part for part in layout_text_parts if part).strip()
	cleaned_text = extracted_layout_text or extracted_text
	extraction_method = "pdfplumber"
	ocr_text = None

	if not _is_useful_text(cleaned_text):
		ocr_text, ocr_debug = extract_pdf_text_with_tesseract(file_path)
		debug_output.extend(ocr_debug)
		if ocr_text:
			extraction_method = "pdfplumber+tesseract"
			cleaned_text = ocr_text

	raw = {
		"file": Path(file_path).name,
		"extraction_method": extraction_method,
		"pages": pages,
	}
	if ocr_text:
		raw["ocr_text"] = ocr_text

	return {
		"extraction_method": extraction_method,
		"extracted_text": cleaned_text,
		"raw_extraction_json": raw,
		"debug_output": debug_output,
	}


def extract_pdf_text_with_tesseract(file_path: str) -> tuple[str | None, list[str]]:
	debug_output = []
	pdftoppm = shutil.which("pdftoppm")
	tesseract = shutil.which("tesseract")

	if not pdftoppm or not tesseract:
		debug_output.append("OCR skipped: pdftoppm or tesseract is not available.")
		return None, debug_output

	with tempfile.TemporaryDirectory() as tmpdir:
		prefix = str(Path(tmpdir) / "page")
		subprocess.run([pdftoppm, "-png", "-r", "200", file_path, prefix], check=True, capture_output=True)

		ocr_parts = []
		for image_path in sorted(Path(tmpdir).glob("page-*.png")):
			completed = subprocess.run(
				[tesseract, str(image_path), "stdout"],
				check=True,
				capture_output=True,
				text=True,
			)
			ocr_parts.append(completed.stdout.strip())

	return "\n\n".join(part for part in ocr_parts if part).strip() or None, debug_output


def extract_image_text_with_tesseract(file_path: str) -> tuple[str | None, list[dict[str, Any]], list[str]]:
	debug_output = []
	tesseract = shutil.which("tesseract")

	if not tesseract:
		debug_output.append("Image OCR skipped: tesseract is not available.")
		return None, [], debug_output

	text_completed = subprocess.run(
		[tesseract, file_path, "stdout"],
		check=True,
		capture_output=True,
		text=True,
	)
	tsv_completed = subprocess.run(
		[tesseract, file_path, "stdout", "tsv"],
		check=True,
		capture_output=True,
		text=True,
	)

	return (
		text_completed.stdout.strip() or None,
		_parse_tesseract_tsv_words(tsv_completed.stdout),
		debug_output,
	)


def _get_pdfplumber():
	try:
		return importlib.import_module("pdfplumber")
	except ImportError:
		frappe.throw(
			_("pdfplumber is required to extract PDF text. Please install project dependencies."),
			frappe.ValidationError,
		)


def _is_pdf(path_or_url: str) -> bool:
	return path_or_url.lower().split("?", 1)[0].endswith(".pdf")


def _is_image(path_or_url: str) -> bool:
	return Path(path_or_url.lower().split("?", 1)[0]).suffix in {
		".bmp",
		".gif",
		".jpeg",
		".jpg",
		".png",
		".tif",
		".tiff",
		".webp",
	}


def _is_useful_text(text: str | None) -> bool:
	return bool(text and len(text.strip()) >= 20)


def _parse_json(value: str | dict | list | None):
	if not value:
		return {}
	if isinstance(value, (dict, list)):
		return value
	try:
		return json.loads(value)
	except Exception:
		return {}


def _get_source_file_preview_url(queue_doc: DocumentQueue) -> str:
	file_doc_name = frappe.db.get_value(
		"File",
		{
			"file_url": queue_doc.source_file,
			"attached_to_doctype": queue_doc.doctype,
			"attached_to_name": queue_doc.name,
		},
		"name",
	)

	if not file_doc_name:
		return queue_doc.source_file

	file_doc = frappe.get_doc("File", file_doc_name)
	return file_doc.unique_url


def _json_safe(value):
	return json.loads(json.dumps(value, default=str))


def _parse_tesseract_tsv_words(tsv: str) -> list[dict[str, Any]]:
	lines = [line for line in (tsv or "").splitlines() if line.strip()]
	if len(lines) <= 1:
		return []

	headers = lines[0].split("\t")
	words = []
	for line in lines[1:]:
		values = line.split("\t")
		row = dict(zip(headers, values, strict=False))
		text = (row.get("text") or "").strip()
		if not text:
			continue

		left = cint(row.get("left"))
		top = cint(row.get("top"))
		width = cint(row.get("width"))
		height = cint(row.get("height"))
		words.append(
			{
				"text": text,
				"x0": left,
				"top": top,
				"x1": left + width,
				"bottom": top + height,
				"confidence": row.get("conf"),
			}
		)

	return words


@frappe.whitelist()
def enqueue_extraction(document_queue: str) -> str:
	task = enqueue_document_extraction(document_queue)
	return task.name
